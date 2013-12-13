module Microphytobenthos_class

! The microphytobenthos class is a subclass of superclass Bethos_Effect. It comprises The effect of
! microphytobenthos on erodibility and crticial bed shear stress.

use BenthosEffect_class

implicit none
type , public, extends (BenthosEffect) :: Microphytobenthos

type (statevariable) , pointer :: BioMass => null()
real (fp)            , pointer :: TauEffect => null()
real (fp)            , pointer :: ErodibilityEffect => null()


contains

 procedure, public, pass :: initialize=> init_microphyt
 procedure, public, pass :: set=> set_microphyt
 procedure, public, pass :: run=> run_microphyt
 procedure, public, pass :: finilize=> fin_micropyht
end type
!private :: init_microphyt, set_microphyt, run_microphyt,fin_micropyht
contains

subroutine init_microphyt (this)

implicit none


class (Microphytobenthos) :: this
integer :: istatus

allocate (character (17) :: this%Species)
allocate (this%BioMass)
allocate (This%BioMass%amount)
!allocate (This%BioMass%Unitt)
allocate (this%TauEffect)
allocate (this%ErodibilityEffect,stat= istatus)
!if (istatus == 0) then
!    write (*,*) 'allocation of ErodibilityEffect was successfull'
!else
!    write (*,*) 'Error , allocation of ErodibilityEffect was NOT successfull'
!end if

end subroutine init_microphyt

subroutine set_microphyt (this)
use BioTypes
implicit none

class (Microphytobenthos)  :: this
real (fp)                  :: Mass
character (len = 4)        :: Unitt
integer                    :: StringLength, UnitNr, istat
logical                    :: opnd, exst


namelist /Microphyto/ Unitt, Mass

this%Species='Microphytobenthos'

inquire ( file = 'microphyt.nml', exist=exst , opened =opnd, Number = UnitNr )
!write (*,*) 'exist ', exst, 'opened ', opnd, ' file unit', UnitNr

if (exst.and.(.not.opnd)) then

 UnitNr = 11
 open (unit = UnitNr, file = 'microphyt.nml', action = 'read ', status = 'old', delim = 'APOSTROPHE')
! write (*,*) ' in Microphytobenthos the file unit ', UnitNr, ' was just opened'

 read (UnitNr, nml=Microphyto, iostat = istat)
 if (istat /= 0 ) write (*,*) ' Error in reading Microphytobenthos data'

elseif (opnd) then

 write (*,*) ' in Microphytobenthos the file unit ', UnitNr, ' already opened'
 read (UnitNr, nml=Microphyto, iostat = istat)

 if (istat /= 0 ) write (*,*) ' Error in reading Microphytobenthos data'

else

 write (*,*) 'ERROR: The input file for Microphytobenthos doesnot exists!'

end if

 this%UnitNr = UnitNr
 write (*,*) ' In Microphytobenthos_class, the amount of Chl biomass is ', Mass
 write (*,*) ' Unit is ', Unitt

 This%BioMass%amount = Mass

StringLength = len_trim (unitt)

if (StringLength /= 0 ) then
    allocate (character(StringLength) :: This%BioMass%Unitt)
    This%BioMass%Unitt = trim (unitt)
end if



close (UnitNr)

end subroutine set_microphyt

subroutine run_microphyt (this)
use Bio_critical_shear_stress
use Bio_erodibility


implicit none

class (Microphytobenthos) :: this

this%TauEffect =  Crit_shear_bioeffect(this%BioMass)
this%ErodibilityEffect = erodibility_bioeffect(this%BioMass)

write (*,*) ' Biotic effect of ', this%Species, ' on tau ( Micro%TauEffect) ', this%TauEffect
write (*,*)
write (*,*) 'Biotic effect of ', this%Species, ' on the Erodibility (Micro%ErodibilityEffect): ', this%ErodibilityEffect
write (*,*)

end subroutine run_microphyt

subroutine fin_micropyht (this)

implicit none

class (Microphytobenthos) :: this
integer                   :: UnitNr
logical                   :: opnd, exst


deallocate (This%BioMass%amount)
deallocate (This%BioMass%Unitt)
deallocate (this%BioMass)
deallocate (this%Species)
deallocate (this%TauEffect)
deallocate (this%ErodibilityEffect)

inquire ( file = 'microphyt.nml', exist=exst , opened =opnd, Number = UnitNr )
if (opnd) close (UnitNr)

end subroutine fin_micropyht


end module Microphytobenthos_class
