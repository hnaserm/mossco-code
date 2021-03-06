!> @brief Implementation of an ESMF toplevel coupling
!>
!> This computer program is part of MOSSCO.
!> @copyright Copyright (C) 2014, Helmholtz-Zentrum Geesthacht
!> @author Carsten Lemmen, <carsten.lemmen@hzg.de>

!
! MOSSCO is free software: you can redistribute it and/or modify it under the
! terms of the GNU General Public License v3+.  MOSSCO is distributed in the
! hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file
! LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms.
!
module toplevel_component

  use esmf

  ! Registration routines for fabm
  use fabm_sediment_component, only : fabmsed_SetServices => SetServices
  use constant_component, only : constant_SetServices => SetServices

  implicit none

  private

  public SetServices

  type(ESMF_GridComp),save  :: fabmComp,constantComp
  type(ESMF_State),save     :: fabmExp, fabmImp, constExp

  contains

  subroutine SetServices(gridcomp, rc)

    type(ESMF_GridComp)  :: gridcomp
    integer, intent(out) :: rc

    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_INITIALIZE, Initialize, rc=rc)
    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_RUN, Run, rc=rc)
    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_FINALIZE, Finalize, rc=rc)

  end subroutine SetServices

  subroutine Initialize(gridComp, importState, exportState, parentClock, rc)
    
    type(ESMF_GridComp)   :: gridComp
    type(ESMF_State)      :: importState
    type(ESMF_State)      :: exportState
    type(ESMF_Clock)      :: parentClock
    integer, intent(out)  :: rc

    type(ESMF_Grid)       :: grid
    type(ESMF_Field)      :: temperatureField
    type(ESMF_FieldBundle) :: fieldBundle
    integer               :: petCount, localPet
    real(ESMF_KIND_R8),dimension(:,:),allocatable :: farray

    call ESMF_LogWrite("Toplevel component initializing ... ",ESMF_LOGMSG_INFO)

    ! Create component, call setservices, and create states
    fabmComp = ESMF_GridCompCreate(name="fabmComp", rc=rc)
    call ESMF_GridCompSetServices(fabmComp,fabmsed_SetServices, rc=rc)
    constantComp = ESMF_GridCompCreate(name="constantComp",rc=rc)
    call ESMF_GridCompSetServices(constantComp,constant_SetServices, rc=rc)
    
    fabmImp = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_IMPORT,name="fabmImp")
    fabmExp = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_EXPORT,name="fabmExp")
    constExp = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_EXPORT,name="constExp")

    call ESMF_GridCompInitialize(constantComp, importState=fabmExp, exportState=fabmImp,clock=parentClock,rc=rc)
    call ESMF_GridCompInitialize(fabmComp, importState=fabmImp, exportState=fabmExp, clock=parentClock, rc=rc)
    call ESMF_GridCompInitialize(constantComp, importState=fabmExp, exportState=constExp,clock=parentClock,rc=rc)

    call ESMF_LogWrite("Toplevel component initialized",ESMF_LOGMSG_INFO) 
    call ESMF_LogFlush()

  end subroutine Initialize

  subroutine Run(gridComp, importState, exportState, parentClock, rc)
    
    type(ESMF_GridComp)   :: gridComp
    type(ESMF_State)      :: importState, exportState
    type(ESMF_Clock)      :: parentClock
    integer, intent(out)  :: rc

    call ESMF_LogWrite("Toplevel component running ... ",ESMF_LOGMSG_INFO)

    do while (.not. ESMF_ClockIsStopTime(parentClock, rc=rc))
      
      call ESMF_GridCompRun(fabmComp, importState=constExp, exportState=fabmExp, clock=parentClock, rc=rc)

      call ESMF_ClockAdvance(parentClock, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      
    enddo 

    call ESMF_LogWrite("Toplevel component finished running. ",ESMF_LOGMSG_INFO)
 
  end subroutine Run

  subroutine Finalize(gridComp, importState, exportState, parentClock, rc)
    
    type(ESMF_GridComp)   :: gridComp
    type(ESMF_State)      :: importState, exportState
    type(ESMF_Clock)      :: parentClock
    integer, intent(out)  :: rc

    call ESMF_LogWrite("Toplevel component finalizing",ESMF_LOGMSG_INFO)

    call ESMF_GridCompFinalize(fabmComp, importState=fabmImp, exportState=fabmExp, &
      clock=parentClock, rc=rc)
    call ESMF_GridCompDestroy(fabmComp, rc=rc)

    call ESMF_GridCompFinalize(constantComp, importState=fabmExp, exportState=fabmImp, &
      clock=parentClock, rc=rc)
    call ESMF_GridCompDestroy(constantComp, rc=rc)

    call ESMF_LogWrite("Toplevel component finalized",ESMF_LOGMSG_INFO)
   
    rc=ESMF_SUCCESS

  end subroutine Finalize

end module toplevel_component
