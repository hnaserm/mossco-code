!> @file fabm0d_driver.F90
!> @brief 3D generic driver for the Framework for Aquatic Biogeochemical Models (FABM)
!>
!> This computer program is part of MOSSCO.
!> @copyright Copyright 2013, 2014, 2015 Helmholtz-Zentrum Geesthacht
!> @author Richard Hofmeister <richard.hofmeister@hzg.de>

!
! MOSSCO is free software: you can redistribute it and/or modify it under the
! terms of the GNU General Public License v3+.  MOSSCO is distributed in the
! hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file
! LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms.
!

!! This class provides a routine to create a pelagic FABM instance (called "pf" here),
!! which initialises FABM and allocates memory for the state variable. The pf instance
!! then these methods:
!!   * set_environment - set the environment forcing
!!   * get_rhs - get the temporal rates
!!   * light - calculate 3d PAR based on radiation at water surface and FABM's extinction
!!   * update_export_states - renew pointers and data (incl. sinking velocities) for export

  module mossco_fabm_pelagic

#define RANGE3D 1:pf%inum,1:pf%jnum,1:pf%knum
#define RANGE2D 1:pf%inum,1:pf%jnum
  use solver_library
  use mossco_strings
  use fabm
  use fabm_types
  use fabm_expressions
  use fabm_standard_variables
  implicit none
  private

  public :: rk
  public mossco_create_fabm_pelagic

  type, extends(type_rhs_driver), public :: type_mossco_fabm_pelagic
    type(type_model),pointer           :: model
    type(export_state_type),dimension(:),pointer :: export_states => null()
    real(rk),dimension(:,:,:),pointer  :: temp,salt,par,dens,current_depth
    real(rk),dimension(:,:,:),pointer  :: layer_height=>null()
    real(rk),dimension(:,:),pointer    :: volume_flux=>null()
    real(rk),dimension(:,:),pointer    :: column_area=>null()
    real(rk),dimension(:,:,:),pointer  :: zi=>null() !> layer interface depth
    real(rk),dimension(:,:,:),pointer  :: cell_per_column_volume=>null()
    logical ,dimension(:,:,:),pointer  :: is_openboundary=>null()
    real(rk),dimension(:,:),pointer    :: wind_sf,taub,par_sf,I_0=>null()
    real(rk),dimension(:,:),pointer    :: albedo=>null()
    real(rk),pointer                   :: decimal_yearday=>null()
    integer                            :: day_of_year,seconds_of_day
    real(rk)                           :: background_extinction=1.0d0/7.9d0 ![1/m] - Jerlov 6
    integer                            :: ndiag
    integer                            :: ndiag_hz
    integer                            :: ndiag_int=0
    integer                            :: ndiag_hz_int=0
    logical                            :: fabm_ready
    type(type_bulk_standard_variable),dimension(:),pointer :: bulk_dependencies => null()
    type(type_horizontal_standard_variable), dimension(:), pointer :: horizontal_dependencies => null()
    real(rk), dimension(:,:,:), pointer  :: horizontal_expression_data => null()
    real(rk), dimension(:,:,:), pointer  :: horizontal_data => null()
    real(rk), dimension(:,:,:,:), pointer:: time_integrated_bulk_variables => null()
    real(rk), dimension(:,:,:), pointer  :: time_integrated_horizontal_variables => null()
    integer, dimension(:), pointer       :: int_idx_from_diag_idx
    integer, dimension(:), pointer       :: int_idx_from_hor_diag_idx
    contains
    procedure :: get_rhs
    procedure :: get_dependencies
    procedure :: set_environment
    procedure :: set_time
    procedure :: light
    procedure :: check_ready
    procedure :: get_export_state_by_id
    procedure :: get_all_export_states
    procedure :: update_export_states
    procedure :: diagnostic_variables
    procedure :: horizontal_diagnostic_variables
    procedure :: integrate_diagnostic_variables
    procedure :: integrate_horizontal_diagnostic_variables
    procedure :: initialize_concentrations
    procedure :: update_pointers
    procedure :: initialize_domain
    procedure :: update_grid
    procedure :: update_expressions
    procedure :: check_expressions
    procedure :: clip_below_minimum
  end type

  type,public :: export_state_type !< pelagic FABM driver type for export states
    character(len=256) :: standard_name=''
    character(len=256) :: units=''
    integer            :: fabm_id=-1
    logical            :: particulate=.false.
    real(rk),dimension(:,:,:),pointer   :: conc => null()
    real(rk),dimension(:,:,:),pointer   :: ws => null()
  end type

  contains

  !> creates instance of pelagic fabm class
  function mossco_create_fabm_pelagic() result(pf)

    type(type_mossco_fabm_pelagic), allocatable :: pf

    integer  :: n
    integer  :: namlst=123
    real(rk) :: dt

    allocate(pf)
    pf%fabm_ready=.false.
    pf%conc => null()
    pf%par => null()
    ! Build FABM model tree.
    pf%model => fabm_create_model_from_file(namlst)

    pf%nvar = size(pf%model%state_variables)
    pf%ndiag = size(pf%model%diagnostic_variables)
    pf%ndiag_hz = size(pf%model%horizontal_diagnostic_variables)
    allocate(pf%int_idx_from_diag_idx(pf%ndiag))
    pf%int_idx_from_diag_idx(:)=-1
    allocate(pf%int_idx_from_hor_diag_idx(pf%ndiag_hz))
    pf%int_idx_from_hor_diag_idx(:)=-1
    do n=1,pf%ndiag
      if ((pf%model%diagnostic_variables(n)%output == output_time_step_averaged) .or. &
          (pf%model%diagnostic_variables(n)%output == output_time_step_integrated)) then
        pf%ndiag_int = pf%ndiag_int+1
        pf%int_idx_from_diag_idx(n) = pf%ndiag_int
      end if
    end do
    do n=1,pf%ndiag_hz
      if ((pf%model%horizontal_diagnostic_variables(n)%output == output_time_step_averaged) .or. &
          (pf%model%horizontal_diagnostic_variables(n)%output == output_time_step_integrated)) then
        pf%ndiag_hz_int = pf%ndiag_hz_int+1
        pf%int_idx_from_hor_diag_idx(n) = pf%ndiag_hz_int
      end if
    end do

    ! initialise the export states and dependencies
    call pf%get_all_export_states()
    call pf%get_dependencies()

  end function mossco_create_fabm_pelagic

  !> initialize domain of pelagic fabm class
  subroutine initialize_domain(pf,inum,jnum,knum,dt,mask)

    class(type_mossco_fabm_pelagic) :: pf
    integer  :: inum,jnum,knum
    real(rk) :: dt
    logical, dimension(1:inum,1:jnum,1:knum), optional :: mask

    type(export_state_type), pointer :: export_state
    integer :: n

    pf%fabm_ready=.false.
    pf%inum=inum
    pf%jnum=jnum
    pf%knum=knum

    ! Send information on spatial domain
    call fabm_set_domain(pf%model,inum,jnum,knum)

    ! set mask (valid data point: mask=.false.)
    ! fabm_set_mask is not used, since MOSSCO does not use a
    ! particular vectorized dimension
    allocate(pf%mask(1:inum,1:jnum,1:knum))
    if (present(mask)) then
      pf%mask=mask
    else
      pf%mask(:,:,:) = .false.
    end if

    ! Allocate array for photosynthetically active radiation (PAR).
    allocate(pf%par(1:inum,1:jnum,1:knum))
    call fabm_link_bulk_data(pf%model,standard_variables%downwelling_photosynthetic_radiative_flux,pf%par)

    ! allocate Albedo array
    allocate(pf%albedo(1:inum,1:jnum))
    pf%albedo = 0.0d0

#if 0
    do n=1,size(pf%export_states)
      export_state => pf%export_states(n)
      !! memory handling should be shifted to component, which has total grid layout
      if (.not.associated(export_state%ws)) then
        allocate(export_state%ws(pf%inum,pf%jnum,pf%knum))
        export_state%ws = 0.0d0
      end if
    end do
#endif

    ! link global time information
    allocate(pf%decimal_yearday)
    pf%decimal_yearday=-999.0d0
    call fabm_link_scalar_data(pf%model, &
      standard_variables%number_of_days_since_start_of_the_year, &
      pf%decimal_yearday)

    call pf%check_expressions()

    ! initialize index mapping and memory for time integrated variables
    if (.not.associated(pf%time_integrated_bulk_variables)) then
      allocate(pf%time_integrated_bulk_variables(pf%inum,pf%jnum,pf%knum,pf%ndiag_int))
      pf%time_integrated_bulk_variables = 0.0d0
    end if
    if (.not.associated(pf%time_integrated_horizontal_variables)) then
      allocate(pf%time_integrated_horizontal_variables(pf%inum,pf%jnum,pf%ndiag_hz_int))
      pf%time_integrated_horizontal_variables = 0.0d0
    end if

  end subroutine initialize_domain

  subroutine initialize_concentrations(pf)
    class(type_mossco_fabm_pelagic) :: pf

    integer :: n

    do n=1,pf%nvar
      pf%conc(:,:,:,n) = pf%model%state_variables(n)%initial_value
    end do

  end subroutine

  subroutine update_pointers(pf)

    class(type_mossco_fabm_pelagic) :: pf

    integer :: n

    do n=1,pf%nvar
      call fabm_link_bulk_state_data(pf%model,n,pf%conc(RANGE3D,n))
    end do

    call fabm_link_bulk_data(pf%model,standard_variables%downwelling_photosynthetic_radiative_flux,pf%par)
    call fabm_link_scalar_data(pf%model, &
      standard_variables%number_of_days_since_start_of_the_year, &
      pf%decimal_yearday)

  end subroutine

  subroutine check_ready(pf)

    class(type_mossco_fabm_pelagic) :: pf

    integer  :: i,j,k
    real(rk) :: rhs(1:pf%nvar),bottom_flux(1:0)

    if (.not.pf%fabm_ready) then
      call fabm_check_ready(pf%model)
      pf%fabm_ready = .true.
    end if
    !> check for I_0 and zi to be associated
    if (.not.associated(pf%zi)) then
      write(0,*) 'layer interface depth not linked yet.'
      stop
    else
      if (.not.associated(pf%layer_height)) then
        !write(0,*) 'allocate layer height'
        allocate(pf%layer_height(pf%inum,pf%jnum,pf%knum))
        call pf%update_grid()
      end if
    end if
    if (.not.associated(pf%I_0)) then
      write(0,*) 'surface light not linked yet.'
      stop
    end if
    !> call fabm_do to fill diagnostic variables and pre-fetch data
    do i=1,pf%inum
      do j=1,pf%jnum
        call fabm_do_surface(pf%model,i,j,pf%knum,rhs(:))
        call fabm_do_bottom(pf%model,i,j,1,rhs(:),bottom_flux(:))
        rhs=0.0_rk
        do k=1,pf%knum
          call fabm_do(pf%model,i,j,k,rhs(:))
        end do
      end do
    end do
    !call pf%update_expressions()

  end subroutine check_ready

  subroutine update_grid(pf)

    class(type_mossco_fabm_pelagic) :: pf

    integer  :: i,j,k

    do k=1,pf%knum
      pf%layer_height(RANGE2D,k) = pf%zi(RANGE2D,k) - pf%zi(RANGE2D,k-1)
    end do

  end subroutine

  subroutine get_rhs(rhs_driver,rhs)

    use fabm
    use fabm_types
    implicit none

    class(type_mossco_fabm_pelagic),intent(inout)     :: rhs_driver
    real(rk),intent(inout),dimension(:,:,:,:),pointer :: rhs

    integer :: n,i,j,k

    rhs=0.0_rk
    !   link state variables
#define RHSRANGE3D 1:rhs_driver%inum,1:rhs_driver%jnum,1:rhs_driver%knum
    do n=1,size(rhs_driver%model%state_variables)
      call fabm_link_bulk_state_data(rhs_driver%model,n,rhs_driver%conc(RHSRANGE3D,n))
    end do

    ! get fluxes through surface and bottom
    ! just to update the pelagic variables
    do j=1,rhs_driver%jnum
      do i=1,rhs_driver%inum
        if (.not.rhs_driver%mask(i,j,rhs_driver%knum)) then
          call fabm_do_surface(rhs_driver%model,i,j,rhs_driver%knum,rhs(i,j,rhs_driver%knum,:))
          rhs(i,j,rhs_driver%knum,:) = rhs(i,j,rhs_driver%knum,:)/rhs_driver%layer_height(i,j,rhs_driver%knum)
        end if
        !if (.not.rhs_driver%mask(i,j,1)) then
        !  call fabm_do_bottom()
        !end if
      end do
    end do

    ! get local rates of change
    do k=1,rhs_driver%knum
      do j=1,rhs_driver%jnum
        do i=1,rhs_driver%inum
          if (.not.rhs_driver%mask(i,j,k)) call fabm_do(rhs_driver%model,i,j,k,rhs(i,j,k,:))
        end do
     end do
    end do

  end subroutine get_rhs

  !> append external bulk dependency
  subroutine add_bulk_dependency(deps, var)
    type(type_bulk_standard_variable),dimension(:), pointer :: deps
    type(type_standard_variable),target                     :: var

    type(type_bulk_standard_variable),dimension(:), pointer :: deps_tmp
    integer :: n_bulk

    if (associated(deps)) then
      n_bulk = size(deps)
      allocate(deps_tmp(n_bulk))
      deps_tmp = deps
      deallocate(deps)
      allocate(deps(n_bulk+1))
      deps(1:n_bulk)=deps_tmp
      deallocate(deps_tmp)
    else
      n_bulk=0
      allocate(deps(1))
    end if

    deps(n_bulk+1)%units = var%units
    deps(n_bulk+1)%name = var%name

  end subroutine

  !> append external horizontal dependency
  subroutine add_horizontal_dependency(deps, var)
    type(type_horizontal_standard_variable),dimension(:), pointer :: deps
    type(type_standard_variable),target                           :: var

    type(type_horizontal_standard_variable),dimension(:), pointer :: deps_tmp
    integer :: n_hor

    if (associated(deps)) then
      n_hor = size(deps)
      allocate(deps_tmp(n_hor))
      deps_tmp = deps
      deallocate(deps)
      allocate(deps(n_hor+1))
      deps(1:n_hor)=deps_tmp
      deallocate(deps_tmp)
    else
      n_hor=0
      allocate(deps(1))
    end if

    deps(n_hor+1)%units = var%units
    deps(n_hor+1)%name = var%name

  end subroutine


  !> get list of external dependencies
  subroutine get_dependencies(pf)
    class(type_mossco_fabm_pelagic) :: pf

    type(type_link), pointer        :: link

    ! get number of external dependencies in FABM,
    ! allocate list of dependencies names (here: required by the driver)
    nullify(pf%horizontal_dependencies)
    nullify(pf%bulk_dependencies)
    allocate(pf%horizontal_dependencies(1))
    pf%horizontal_dependencies(1)=standard_variables%surface_downwelling_photosynthetic_radiative_flux

    !> add required dependencies
    link => pf%model%links_postcoupling%first
    do while (associated(link))
      if (.not.link%target%read_indices%is_empty().and.link%target%state_indices%is_empty()) then
        select case (link%target%domain)
          case (domain_bulk)
            if (.not.associated(pf%model%data(link%target%read_indices%pointers(1)%p)%p) &
                .and..not.(link%target%presence==presence_internal) &
                .and.associated(link%target%standard_variable)) then
              call add_bulk_dependency(pf%bulk_dependencies,link%target%standard_variable)
            end if
    case (domain_horizontal,domain_bottom,domain_surface)
            if (.not.associated(pf%model%data_hz(link%target%read_indices%pointers(1)%p)%p) &
                .and..not.(link%target%presence==presence_internal) &
                .and.associated(link%target%standard_variable)) then
              if (trim(link%target%standard_variable%name) == "surface_downwelling_photosynthetic_radiative_flux") then
                 link => link%next
                 cycle
              end if
              call add_horizontal_dependency(pf%horizontal_dependencies,link%target%standard_variable)
            end if
          case (domain_scalar)
            if (.not.associated(pf%model%data_scalar(link%target%read_indices%pointers(1)%p)%p) &
                .and..not.(link%target%presence==presence_internal) &
                .and.associated(link%target%standard_variable)) then
            end if
        end select
      end if
      link => link%next
    end do

  end subroutine


  !> set global time
  subroutine set_time(pf,day_of_year,seconds_of_day)
    class(type_mossco_fabm_pelagic) :: pf
    integer :: day_of_year, seconds_of_day

    pf%day_of_year = day_of_year
    pf%seconds_of_day = seconds_of_day
    pf%decimal_yearday = day_of_year-1.0d0 + dble(seconds_of_day)/86400

  end subroutine set_time


  !> set environment forcing for FABM
  subroutine set_environment(pf,varname,ptr_bulk,ptr_horizontal,ptr_scalar)
    class(type_mossco_fabm_pelagic) :: pf

    character(len=*), intent(in)                  :: varname
    real(rk), dimension(:,:,:), optional, pointer :: ptr_bulk
    real(rk), dimension(:,:), optional, pointer   :: ptr_horizontal
    real(rk), optional, pointer                   :: ptr_scalar

    type (type_bulk_variable_id)            :: bulk_id
    type (type_horizontal_variable_id)      :: horizontal_id
    type (type_scalar_variable_id)          :: scalar_id

    ! read name of import state and get FABM's id
    if (present(ptr_bulk)) then
      bulk_id = fabm_get_bulk_variable_id(pf%model,varname)
      ! link data if variable is used
      if (fabm_is_variable_used(bulk_id)) call fabm_link_bulk_data(pf%model,bulk_id,ptr_bulk(RANGE3D))
      if (varname == 'cell_thickness') pf%layer_height => ptr_bulk(RANGE3D)

    else if (present(ptr_horizontal)) then
      horizontal_id = fabm_get_horizontal_variable_id(pf%model,varname)
      ! link data if variable is used
      if (fabm_is_variable_used(horizontal_id)) call fabm_link_horizontal_data(pf%model,horizontal_id,ptr_horizontal(RANGE2D))
      ! keep link to necessary surface radiation
      if (varname == 'surface_downwelling_photosynthetic_radiative_flux') pf%I_0 => ptr_horizontal

    else if (present(ptr_scalar)) then
      scalar_id = fabm_get_scalar_variable_id(pf%model,varname)
      ! link data if variable is used
      if (fabm_is_variable_used(scalar_id)) call fabm_link_scalar_data(pf%model,scalar_id,ptr_scalar)

    end if

  end subroutine set_environment


  !> Initializes a pelagic FABM export state by FABM state_variable id
  function get_export_state_by_id(pf,fabm_id) result(export_state)
    class(type_mossco_fabm_pelagic) :: pf
    type(export_state_type) :: export_state
    integer, intent(in)     :: fabm_id
    integer                 :: n

    export_state%fabm_id=fabm_id
    export_state%conc => null()
  !  !! memory handling should be shifted to component, which has total grid layout
  !  export_state%conc => pf%conc(:,:,:,export_state%fabm_id)
  !  allocate(export_state%ws(pf%inum,pf%jnum,pf%knum))
  !  export_state%ws = 0.0d0
    !> first check for present standard name
    if (pf%model%state_variables(fabm_id)%standard_variable%name/='') then
      export_state%standard_name = &
        trim(pf%model%state_variables(fabm_id)%standard_variable%name)
      export_state%units = &
        trim(pf%model%state_variables(fabm_id)%standard_variable%units)
    else
    !> otherwise use CF-ed version of long_name
      export_state%standard_name = only_var_name( &
            pf%model%state_variables(fabm_id)%long_name)
      export_state%units = pf%model%state_variables(fabm_id)%units
    end if
  end function get_export_state_by_id

!> Initializes a pelagic FABM export state by FABM variable name

   function get_export_state_from_variable_name(pf,varname) result(export_state)
     class(type_mossco_fabm_pelagic) :: pf
     type(export_state_type)         :: export_state
     character(len=256), intent(in)  :: varname
     integer                         :: n,fabm_id

     fabm_id=-1
     do n=1,size(pf%model%state_variables)
       if (trim(pf%model%state_variables(n)%name).eq.trim(varname)) &
           fabm_id=n
     end do
     do n=1,size(pf%model%state_variables_ben)
       if (trim(pf%model%state_variables_ben(n)%name).eq.trim(varname)) &
           fabm_id=n
     end do
     export_state = pf%get_export_state_by_id(fabm_id)
   end function get_export_state_from_variable_name


  !> create a list of export states from FABM state_variables
  subroutine get_all_export_states(pf)
  class(type_mossco_fabm_pelagic) :: pf
    integer  :: n,fabm_id

    allocate(pf%export_states(pf%nvar))
    do fabm_id=1,pf%nvar
      pf%export_states(fabm_id) = pf%get_export_state_by_id(fabm_id)
    end do
  !> @todo: add benthic state variables

  end subroutine get_all_export_states

  !> update pelagic FABM export states pointers and sinking velocities using a list of export states

  subroutine update_export_states(pf,update_sinking)

    class(type_mossco_fabm_pelagic) :: pf
    logical,optional :: update_sinking

    real(rk),dimension(pf%inum,pf%jnum,pf%knum,pf%nvar) :: wstmp
    real(rk),dimension(:,:,:),pointer :: p3d

    type(export_state_type),pointer :: export_state
    integer :: n,i,j,k
    integer,dimension(4) :: lbnd
    logical :: update_sinking_eff

    update_sinking_eff=.true.
    if (present(update_sinking)) update_sinking_eff=update_sinking
    if (update_sinking_eff) then
      do i=1,pf%inum
        do j=1,pf%jnum
          do k=1,pf%knum
            call fabm_get_vertical_movement(pf%model,i,j,k,wstmp(i,j,k,:))
          end do
        end do
      end do
    end if
    lbnd = lbound(pf%conc)
    do n=1,size(pf%export_states)
      export_state => pf%export_states(n)
#if 0
      export_state%conc(lbnd(1):,lbnd(2):,lbnd(3):) => pf%conc(:,:,:,export_state%fabm_id)
#else
      p3d => pf%conc(:,:,:,export_state%fabm_id)
      export_state%conc(lbnd(1):,lbnd(2):,lbnd(3):) => p3d
#endif
      if (update_sinking_eff) then
        export_state%ws(RANGE3D) = wstmp(:,:,:,export_state%fabm_id)
      end if
    end do
    !> @todo add benthic state variables
  end subroutine update_export_states

  !> fabm_pelagic_diagnostic_variables
  !!
  !! The function returns a pointer to the 3d diagnostic variables.
  !! So far, only bulk diagnostic variables are supported. The function is a
  !! wrapper of the related FABM function.

  function diagnostic_variables(pf,n) result(diag)
    implicit none

    class(type_mossco_fabm_pelagic)      :: pf
    integer,intent(in)                   :: n
    real(rk),dimension(:,:,:),pointer    :: diag

    if (pf%model%diagnostic_variables(n)%output == output_none) then
      diag => null()
    elseif (pf%model%diagnostic_variables(n)%output == output_instantaneous) then
      diag => fabm_get_bulk_diagnostic_data(pf%model,n)
    else
      diag => pf%time_integrated_bulk_variables(:,:,:,pf%int_idx_from_diag_idx(n))
    end if
  end function diagnostic_variables

  subroutine integrate_diagnostic_variables(pf,dt)
    implicit none

    class(type_mossco_fabm_pelagic)      :: pf
    real(rk)                             :: dt
    integer                              :: n,nn
    real(rk),dimension(:,:,:),pointer    :: diag

    do n=1,pf%ndiag
      nn = pf%int_idx_from_diag_idx(n)
      if (nn == -1) cycle
      diag => fabm_get_bulk_diagnostic_data(pf%model,n)
      pf%time_integrated_bulk_variables(:,:,:,nn) = pf%time_integrated_bulk_variables(:,:,:,nn) + dt*diag(:,:,:)
    end do
  end subroutine integrate_diagnostic_variables

  !> horizontal_diagnostic_variables
  !!
  !! The function returns a pointer to the 2d diagnostic variables.
  !! So far, only bulk diagnostic variables are supported. The function is a
  !! wrapper of the related FABM function.

  function horizontal_diagnostic_variables(pf,n) result(diag_hz)
    implicit none

    class(type_mossco_fabm_pelagic)    :: pf
    integer,intent(in)                 :: n
    real(rk),dimension(:,:),pointer    :: diag_hz

    if (pf%model%horizontal_diagnostic_variables(n)%output == output_none) then
      diag_hz => null()
    elseif (pf%model%horizontal_diagnostic_variables(n)%output == output_instantaneous) then
      diag_hz => fabm_get_horizontal_diagnostic_data(pf%model,n)
    else
      diag_hz => pf%time_integrated_horizontal_variables(:,:,pf%int_idx_from_hor_diag_idx(n))
    end if
  end function horizontal_diagnostic_variables

  subroutine integrate_horizontal_diagnostic_variables(pf,dt)
    implicit none

    class(type_mossco_fabm_pelagic)      :: pf
    real(rk)                             :: dt
    integer                              :: n,nn
    real(rk),dimension(:,:),pointer      :: diag

    do n=1,pf%ndiag_hz
      nn = pf%int_idx_from_hor_diag_idx(n)
      if (nn == -1) cycle
      diag => fabm_get_horizontal_diagnostic_data(pf%model,n)
      pf%time_integrated_horizontal_variables(:,:,nn) = pf%time_integrated_horizontal_variables(:,:,nn) + dt*diag(:,:)
    end do
  end subroutine integrate_horizontal_diagnostic_variables

   !> Calculate photosynthetically active radiation (PAR) and short wave
   !! radiation (SWR) over entire column, using surface short wave radiation,
   !! and background and biotic extinction.
   subroutine light(pf)

     class(type_mossco_fabm_pelagic)     :: pf
     integer  :: i,j,k
     real(rk) :: bioext(1:pf%inum,1:pf%jnum,1:pf%knum),localext

     bioext = 0.0_rk

     do i=1,pf%inum
       do j=1,pf%jnum
         do k=pf%knum,2,-1
           call fabm_get_light_extinction(pf%model,i,j,k,localext)

           ! Add the extinction of the first half of the grid box.
           bioext(i,j,k) = bioext(i,j,k) + &
             (localext+pf%background_extinction)*0.5_rk*pf%layer_height(i,j,k)

           ! Add the extinction of the second half of the grid box.
           bioext(i,j,k-1) = bioext(i,j,k) + &
             (localext+pf%background_extinction)*0.5_rk*pf%layer_height(i,j,k)
         end do
         ! Add te extinction of the upper, last layer
         call fabm_get_light_extinction(pf%model,i,j,1,localext)
         bioext(i,j,1) = bioext(i,j,1) + &
           (localext+pf%background_extinction)*0.5_rk*pf%layer_height(i,j,1)

         pf%par(i,j,:) = pf%I_0(i,j) * (1.0d0-pf%albedo(i,j)) * exp(-bioext(i,j,:))
       end do
     end do

   end subroutine light


   subroutine check_expressions(pf)
     class(type_mossco_fabm_pelagic) :: pf
     class(type_expression),pointer  :: expression
     integer                         :: n

      n = 0
      expression => pf%model%root%first_expression
      do while (associated(expression))
         select type (expression)
            class is (type_vertical_integral)
               n = n + 1
         end select
         expression => expression%next
      end do

      allocate(pf%horizontal_expression_data(1:pf%inum,1:pf%jnum,n))
      pf%horizontal_expression_data = 0.0d0

      n = 0
      expression => pf%model%root%first_expression
      do while (associated(expression))
         select type (expression)
            class is (type_vertical_integral)
               n = n + 1
               call fabm_link_horizontal_data(pf%model,trim(expression%output_name),pf%horizontal_expression_data(:,:,n))
         end select
         expression => expression%next
      end do
   end subroutine check_expressions

   subroutine update_expressions(pf)
     class(type_mossco_fabm_pelagic) :: pf
     class(type_expression),pointer  :: expression
     integer                         :: n

     n = 0
     expression => pf%model%root%first_expression
     do while (associated(expression))
       select type (expression)
         class is (type_vertical_integral)
           n = n + 1
           pf%horizontal_expression_data(:,:,n) = calculate_vertical_mean(expression,pf%inum,pf%jnum)
       end select
       expression => expression%next
     end do

   contains

     function calculate_vertical_mean(expression,inum,jnum) result(vertmean)
       class(type_vertical_integral),intent(in)    :: expression
       integer, intent(in)                         :: inum,jnum
       real(rk), dimension(1:inum,1:jnum)          :: vertmean
       real(rk), dimension(1:inum,1:jnum)          :: depth
       real(rk), dimension(1:inum,1:jnum,1:pf%knum):: weights
       logical, dimension(1:inum,1:jnum)           :: started
       integer                                     :: i,j,k

       ! Loop over all levels, surface to bottom, and compute vertical mean.
       depth = 0.0d0
       weights = 0.0d0
       started = .false.
       do k=pf%knum,1,-1
         depth = depth + pf%layer_height(:,:,k)
         do i=1,inum
           do j=1,jnum
             if (.not.started(i,j)) then
               ! Not yet at minimum depth before
               if (depth(i,j)>=expression%minimum_depth) then
                 ! Now crossing minimum depth interface
                 started(i,j) = .true.
                 weights(i,j,k) = depth(i,j)-expression%minimum_depth
               end if
             else
             ! Beyond minimum depth, not yet at maximum depth before
             weights(i,j,k) = pf%layer_height(i,j,k)
             end if
             if (depth(i,j)>expression%maximum_depth) then
               ! Now crossing maximum depth interface; subtract part of layer height that is not included
               weights(i,j,k) = weights(i,j,k) - (depth(i,j)-expression%maximum_depth)
               exit
             end if
           end do
         end do
       end do
       do i=1,inum
         do j=1,jnum
           if (expression%average) weights(i,j,:) = weights(i,j,:)/(min(expression%maximum_depth,depth(i,j))-expression%minimum_depth)
         end do
       end do
       vertmean = sum(pf%model%data(expression%in)%p(:,:,:)*weights,dim=3)
     end function calculate_vertical_mean

   end subroutine update_expressions

   subroutine clip_below_minimum(pf)
     class(type_mossco_fabm_pelagic) :: pf
     integer                         :: i,j,k,n

      ! reset concentrations to mininum_value
      do n=1,pf%nvar
        do k=1,pf%knum
          do j=1,pf%jnum
            do i=1,pf%inum
              if (pf%conc(i,j,k,n) .lt. pf%model%state_variables(n)%minimum) then
                pf%conc(i,j,k,n) = pf%model%state_variables(n)%minimum
              end if
            end do
          end do
        end do
      end do
   end subroutine clip_below_minimum

  end module mossco_fabm_pelagic

