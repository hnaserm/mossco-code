import yaml
import sys
import os

if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = 'constant_constant_constant.yaml'

print sys.argv, len(sys.argv)
if not os.path.exists(filename):
    print 'File ' + filename + ' does not exist.'
    exit(1)
    
print 'Using ' + filename + ' ...' 

fid = file(filename,'rU')
config = yaml.load(fid)
fid.close()

# Search for the key with name "coupling".  If part of the filename is the word "coupling" then assume that the first item on the list read is the name of the coupling
coupling_name = 'coupling'
variables = []
coupling_properties = []

if config.has_key('author'):
    author = config.pop('author')
else:
    author = 'Carsten Lemmen, <carsten.lemmen@hzg.de>'

if config.has_key('copyright'):
    copyright = config.pop('copyright')
else:
    copyright = 'Copyright (C) 2014, Helmholtz-Zentrum Geesthacht'

coupling = config.pop("coupling")

componentList=[]
intervals =[]
directions = []
couplingList=[]
couplerList=[]

for item in coupling:
    if type(item) is dict:
        if item.has_key("components"):
            couplingList.append([item["components"][0], item["components"][-1]])
            componentList.extend(item["components"])
            if item.has_key("interval"):
                intervals.append(item["interval"])
            else:
                intervals.append("60 min")
            if item.has_key("direction"):
                directions.append(item["direction"])
    else:
        print 'Warning, dictionary expcted for item ' + item

print couplingList
componentSet=set(componentList)
couplerSet=set(couplerList)

# Done parsint ghte list, now write the new toplevel_compnent file
       
outfilename = 'toplevel_coupling.F90'
fid = file(outfilename,'w')

fid.write('''
!> @brief Implementation of an ESMF toplevel coupling
!>
!> Do not edit this file, it is automatically generated by
''')
fid.write('!> the call \'python ' + sys.argv[0] + ' ' + filename + '\'')
fid.write('''
!>
!> This computer program is part of MOSSCO. 
''')
fid.write('!> @copyright ' + copyright + '\n')
fid.write('!> @author ' + author + '\n')
fid.write('''
!
! MOSSCO is free software: you can redistribute it and/or modify it under the
! terms of the GNU General Public License v3+.  MOSSCO is distributed in the
! hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file
! LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms.
!
''')

fid.write('module ' + 'toplevel_coupling\n') 
fid.write('''
  use esmf
  use mossco_variable_types
  use mossco_state\n
''')

for item in componentSet:
    fid.write('  use ' + item + '_component,\t\tonly : ' + item + '_SetServices => SetServices \n')

fid.write('\n  implicit none\n\n  private\n\n  public SetServices\n')
fid.write('''
  type(ESMF_GridComp),dimension(:),save, allocatable :: gridCompList
  type(ESMF_CplComp),dimension(:), save, allocatable :: cplCompList
  type(ESMF_State), dimension(:),  save, allocatable :: exportStates, importStates
  type(ESMF_Alarm), dimension(:),  save, allocatable :: cplAlarmList

''')

for item in couplerSet:
    fid.write('  type(ESMF_CplComp),\tsave\t:: ' + item + 'Comp\n')    
for item in componentSet:
    fid.write('  type(ESMF_GridComp),\tsave\t:: ' + item + 'Comp\n')    
for item in componentSet:
    fid.write('  type(ESMF_State),\tsave\t:: ' + item + 'ExportState, ' + item + 'ImportState\n')    

fid.write('''

  contains

  !> Provide an ESMF compliant SetServices routine, which defines
  !! entry points for Init/Run/Finalize
  subroutine SetServices(gridcomp, rc)
  
    type(ESMF_GridComp)  :: gridcomp
    integer, intent(out) :: rc

    rc = ESMF_SUCCESS

    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_INITIALIZE, Initialize, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_RUN, Run, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    call ESMF_GridCompSetEntryPoint(gridcomp, ESMF_METHOD_FINALIZE, Finalize, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    rc=ESMF_SUCCESS
    
  end subroutine SetServices

  !> Initialize the coupling
  !!
  subroutine Initialize(gridComp, importState, exportState, parentClock, rc)

    implicit none

    type(ESMF_GridComp)  :: gridComp
    type(ESMF_State)     :: importState, exportState
    type(ESMF_Clock)     :: parentClock
    integer, intent(out) :: rc

    character(len=19)       :: timestring
    type(ESMF_Time)         :: clockTime, startTime, stopTime, currTime
    type(ESMF_Time)         :: ringTime, time
    type(ESMF_TimeInterval) :: timeInterval, timeStep, alarmInterval
    real(ESMF_KIND_R8)      :: dt
     
    integer(ESMF_KIND_I4)  :: numGridComp, numCplComp
    integer(ESMF_KIND_I4)  :: alarmCount, numCplAlarm, i
    type(ESMF_Alarm), dimension(:), allocatable :: alarmList !> @todo shoudl this be a pointer?
    character(ESMF_MAXSTR) :: name
    type(ESMF_Alarm)       :: childAlarm
    type(ESMF_Clock)       :: childClock
    type(ESMF_Clock)       :: clock !> This component's internal clock
    logical                :: clockIsPresent
     
    ! Create a local clock, set its parameters to those of the parent clock
    clock = ESMF_ClockCreate(parentClock, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    
    call ESMF_ClockSet(clock, name=\'toplevel_coupling clock\', rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    
    call ESMF_GridCompSet(gridComp, clock=clock, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    ! Create all gridded components and their states
''')
fid.write('    numGridComp = ' + str(len(componentSet)) + '\n')
fid.write('    allocate(gridCompList(numGridComp))\n')
fid.write('    allocate(importStates(numGridComp))\n')
fid.write('    allocate(exportStates(numGridComp))\n\n')

i=0
for item in componentSet:
    fid.write('    gridCompList(' + str(i+1) + ') = ESMF_GridCompCreate(name=\'' + item + 'Comp\', rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    fid.write('    call ESMF_GridCompSetServices(gridCompList(' + str(i+1) + '), ' + item + '_SetServices, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n\n')

    fid.write('    exportStates(' + str(i+1) + ') = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_UNSPECIFIED,name=\'' + item + 'ExportState\')\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    fid.write('    importStates(' + str(i+1) + ') = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_UNSPECIFIED,name=\'' + item + 'ImportState\')\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n\n')
    i += 1

if len(couplerSet)>0:
    fid.write('    ! Create all coupler components')
    fid.write('    numCplComp  = '  + str(len(couplerSet)) + '\n\n')
for item in couplerSet:
    fid.write('    cplCompList(' + str(i+1) + ') = ESMF_CplCompCreate(name=\'' + item + 'Comp\', rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    fid.write('    call ESMF_CplCompSetServices(cplCompList(' + str(i+1) + '), ' + item + '_SetServices, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n\n')

fid.write('    ! Initialize all gridded and coupler components\n')
i = 0
for item in componentSet:
    fid.write('    call ESMF_GridCompInitialize(gridCompList(' + str(i+1) + '), importState=importStates(' + str(i+1) + '), &\n')
    fid.write('      exportState=exportStates(' + str(i+1) + '), clock=clock, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    i += 1
fid.write('\n')
for item in couplerSet:
    fid.write('    call ESMF_CplCompInitialize(cplCompList(' + str(i+1) + '), importState=importStates(' + str(i+1) + '), &\n')
    fid.write('      exportState=exportStates(' + str(i+1) + '), clock=clock, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')

fid.write('    numCplAlarm = ' + str(len(couplingList)) + '\n')
fid.write('    allocate(cplAlarmList(numCplAlarm))\n')
fid.write('''

    !! Set the coupling alarm starting from current time of local clock
    call ESMF_ClockGet(clock,startTime=startTime, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
 
''')
for i in range(0,len(couplingList)):
    string = intervals[i].split()
    number = string[0]
    if len(string)>1:
        unit = string[1]
    else:
        unit = 'h'
    fid.write('    call ESMF_TimeIntervalSet(alarmInterval,' + unit + '=' + number + ',rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)\n\n')  
    fid.write('    cplAlarmList(' + str(i+1) + ')=ESMF_AlarmCreate(clock=clock,ringTime=startTime+alarmInterval, &\n')
    alarmName = str(couplingList[i][0]) + '--' + str(couplingList[i][-1]) + '--cplAlarm'
    fid.write('      ringInterval=alarmInterval, name=\'' + alarmName + '\', rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)\n')
    
    fid.write('''
    !! Copy this alarm to all children as well
    do i=1,numGridComp
      call ESMF_GridCompGet(gridCompList(i),name=name, rc=rc) 
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      
    ''')
    fid.write('  if (trim(name)==\'' + str(couplingList[i][0]) + 'Comp\' .or. trim(name)==\'' + str(couplingList[i][-1]) + 'Comp\') then')
    fid.write('''
        call ESMF_GridCompGet(gridCompList(i), clockIsPresent=clockIsPresent, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
        if (clockIsPresent) then
          call ESMF_GridCompGet(gridCompList(i), clock=childClock, rc=rc) 
        else
          call ESMF_LOGWRITE('Creating clock for '//trim(name)//', this should have been done by the component.', &
            ESMF_LOGMSG_WARNING)        
        
          childClock=ESMF_ClockCreate(clock=clock, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
          
          call ESMF_GridCompSet(gridCompList(i),clock=childClock, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        endif      
    ''')    
    fid.write('    childAlarm=ESMF_AlarmCreate(cplAlarmList(' + str(i+1) + '), rc=rc)')
    fid.write('''
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

        call ESMF_AlarmSet(childAlarm, clock=childClock)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
      endif
    enddo
    ''')
      
 
fid.write('''
      
    !! Search the clock for next ringing Alarm and save the ring time in 
    !! the variable time
    call ESMF_ClockGetAlarmList(clock,ESMF_ALARMLIST_ALL,alarmCount=alarmCount,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    allocate(alarmList(alarmCount))
    
    call ESMF_ClockGetAlarmList(clock,ESMF_ALARMLIST_ALL,alarmList=alarmList,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    if (size(alarmList) > 0) then
      call ESMF_TimeSet(time,rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      call ESMF_TimeSet(ringTime,rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
 
      call ESMF_AlarmGet(alarmList(1),ringTime=time,rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      !call ESMF_AlarmPrint(alarmList(1))
    endif
      
    do i=2,size(alarmList)
      call ESMF_AlarmGet(alarmList(i),ringTime=ringTime,rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      if (ringtime<time) time=ringTime
      !call ESMF_AlarmPrint(alarmList(i))
    enddo
    if (allocated(alarmList)) deallocate(alarmList)
    
    !! Set the timestep such that it corresponds to the time until the 
    !! first ringing alarm    
    call ESMF_TimeSet(currTime,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
     
    call ESMF_ClockGet(clock,currTime=currTime,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    call ESMF_ClockSet(clock,timeStep=time-currTime,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    
    call ESMF_LogWrite("toplevel_coupler initialized", ESMF_LOGMSG_INFO)

  end subroutine Initialize

  subroutine Run(gridComp, importState, exportState, parentClock, rc)

    type(ESMF_GridComp)  :: gridComp
    type(ESMF_State)     :: importState, exportState
    type(ESMF_Clock)     :: parentClock
    integer, intent(out) :: rc

    character(len=19)       :: timestring
    type(ESMF_Time)         :: stopTime, currTime, ringTime, time
    type(ESMF_TimeInterval) :: timeInterval
    integer(ESMF_KIND_I8)   :: advanceCount,  i, j
    integer(ESMF_KIND_I4)   :: alarmCount, petCount, localPet
    integer(ESMF_KIND_I4)   :: numGridComp, numCplComp, hours
    
    type(ESMF_Alarm), dimension(:), allocatable, save :: alarmList
    type(ESMF_Alarm)        :: childAlarm
    type(ESMF_Clock)        :: childClock, clock
    logical                 :: clockIsPresent
    
    character(len=ESMF_MAXSTR) :: message, compName, name

    call ESMF_GridCompGet(gridComp,petCount=petCount,localPet=localPet,name=name, &
      clockIsPresent=clockIsPresent, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    if (.not.clockIsPresent) then
      call ESMF_LogWrite('Required clock not found in '//trim(name), ESMF_LOGMSG_ERROR)
      call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    endif
 
    call ESMF_GridCompGet(gridComp, clock=clock, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    call ESMF_ClockGet(clock,currTime=currTime, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

    call ESMF_TimeGet(currTime,timeStringISOFrac=timestring)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

!#ifdef DEBUG
    write(message,'(A)') trim(timestring)//' '//trim(name)//' running ...'
    call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)
!#endif

    numGridComp=ubound(gridCompList,1)-lbound(gridCompList,1)+1
    
   call ESMF_ClockGetAlarmList(clock, alarmListFlag=ESMF_ALARMLIST_ALL, &
     alarmCount=alarmCount, rc=rc)
    
    if (allocated(alarmList)) then
      if (size(alarmList)<alarmCount) then
        deallocate(alarmList)
        allocate(alarmList(alarmCount))
      endif
    else 
      allocate(alarmList(alarmCount))
    endif
   
    !! Run until the clock's stoptime is reached
    do 

      call ESMF_ClockGet(clock,currTime=currTime, stopTime=stopTime, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      
      if (currTime>stopTime) then
        call ESMF_LogWrite('Clock out of scope in '//trim(compName), ESMF_LOGMSG_ERROR)
        call ESMF_FINALIZE(endflag=ESMF_END_ABORT, rc=rc)
      endif

      !! Loop through all components and check whether their clock is currently at the 
      !! same time as my own clock's currTime
      do i=1,numGridComp
        !! Determine for each child the clock    
        call ESMF_GridCompGet(gridCompList(i),name=compName, clockIsPresent=clockIsPresent, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

        if (.not.clockIsPresent) then
          call ESMF_LogWrite('Required clock not found in '//trim(compName), ESMF_LOGMSG_ERROR)
          call ESMF_FINALIZE(endflag=ESMF_END_ABORT, rc=rc)
        endif

        call ESMF_GridCompGet(gridCompList(i), clock=childClock, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
  
        call ESMF_ClockGet(childClock,currTime=time, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

        if (time>currTime) exit
        
        !! Run here all components that have stopped at currTime
        !! Find the child's alarm list, get the interval to the next ringing alarm
        !! and run the component for the interval until that alarm
   
        call ESMF_ClockGetAlarmList(childClock, alarmListFlag=ESMF_ALARMLIST_ALL, &
          alarmCount=alarmCount, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

        if (alarmCount==0) then
          call ESMF_LogWrite('No alarm not found in '//trim(compName), ESMF_LOGMSG_WARNING)
          timeInterval=stopTime-currTime
        else                 
          call ESMF_ClockGetAlarmList(childClock, alarmListFlag=ESMF_ALARMLIST_ALL, &
             alarmList=alarmList, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
          call ESMF_AlarmGet(alarmList(1), ringTime=ringTime, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
          do j=2,alarmCount        
            call ESMF_AlarmGet(alarmList(j), ringTime=time, rc=rc)
            if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
     
            if (time<ringTime) ringTime=time
          enddo 

          timeInterval=ringTime-currTime
        endif
        
        call ESMF_ClockSet(childClock, stopTime=ringTime, rc=rc) 
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

        !call ESMF_ClockSet(clock, stopTime=ringTime, rc=rc) 
        !if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

        call ESMF_TimeIntervalGet(timeInterval, h=hours, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
        
        write(message,'(A,A,G6.2,A)') trim(timeString)//' calling '//trim(compName), &
          ' to run for ', hours, ' h'
        call ESMF_LogWrite(trim(message),ESMF_LOGMSG_INFO, rc=rc);
        
        call ESMF_GridCompRun(gridCompList(i),importState=importStates(i),&
          exportState=exportStates(i), clock=clock, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      enddo

      !! Now that all child components have been started, find out the minimum time
      !! to the next coupling and use this as a time step for my own clock Advance
      call ESMF_ClockGetAlarmList(clock, alarmListFlag=ESMF_ALARMLIST_ALL, &
        alarmCount=alarmCount, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

      if (alarmCount==0) then
        call ESMF_LogWrite('No alarm not found in '//trim(compName), ESMF_LOGMSG_WARNING)
        timeInterval=stopTime-currTime
      else                 
        call ESMF_ClockGetAlarmList(clock, alarmListFlag=ESMF_ALARMLIST_ALL, &
          alarmList=alarmList, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
        call ESMF_AlarmGet(alarmList(1), ringTime=ringTime, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
        do j=2,alarmCount        
          call ESMF_AlarmGet(alarmList(j), ringTime=time, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
     
          if (time<ringTime) ringTime=time
        enddo 

        timeInterval=ringTime-currTime
      endif

      call ESMF_TimeGet(ringTime,timeStringISOFrac=timestring, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

!#ifdef DEBUG 
      write(message,'(A)') trim(name)//' stepping to '//trim(timeString)
      call ESMF_LogWrite(trim(message),ESMF_LOGMSG_INFO, rc=rc);
!#endif

      call ESMF_ClockSet(clock, timeStep=timeInterval, rc=rc) 
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      
      call ESMF_ClockAdvance(clock, rc=rc) 
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
   
      if (ESMF_ClockIsStopTime(clock, rc=rc)) exit
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)           
    enddo

    call ESMF_ClockGet(clock, currTime=currTime, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    call ESMF_TimeGet(currTime,timeStringISOFrac=timestring, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

!#ifdef DEBUG 
    write(message,'(A,A)') trim(timeString)//' '//trim(name), &
          ' finished running.'
    call ESMF_LogWrite(trim(message),ESMF_LOGMSG_INFO, rc=rc);
!#endif

  end subroutine Run

  subroutine Finalize(gridComp, importState, exportState, parentClock, rc)
    type(ESMF_GridComp)  :: gridComp
    type(ESMF_State)     :: importState, exportState
    type(ESMF_Clock)     :: parentClock
    integer, intent(out) :: rc

    type(ESMF_Clock)     :: clock
    logical              :: clockIsPresent
''')
i=0
for item in componentSet:
    fid.write('    call ESMF_GridCompDestroy(gridCompList(' + str(i+1) + '), rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    i += 1
i=0
for item in couplerSet:
    fid.write('    call ESMF_CplCompDestroy(cplCompList(' + str(i+1) + '), rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    i += 1
fid.write('''
    if (allocated(gridCompList)) deallocate(gridCompList) 
    if (allocated(cplCompList))  deallocate(cplCompList) 
    if (allocated(exportStates)) deallocate(exportStates) 
    if (allocated(importStates)) deallocate(importStates) 
    if (allocated(cplAlarmList)) deallocate(cplAlarmList)

    call ESMF_GridCompGet(gridComp, clockIsPresent=clockIsPresent, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        
    if (clockIsPresent) then
      call ESMF_GridCompGet(gridComp, clock=clock, rc=rc)
      call ESMF_ClockDestroy(clock,rc=rc)
    endif
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

  end subroutine Finalize

end module toplevel_coupling
''')

fid.close()

outfilename='Makefile.coupling'
fid = file(outfilename,'w')

fid.write('# This Makefile is part of MOSSCO\n#\n')
fid.write('# Do not edit this file, it is automatically generated by\n')
fid.write('# the call \'python ' + sys.argv[0] + ' ' + filename + '\'\n#\n')
fid.write('# @copyright ' + copyright + '\n')
fid.write('# @author ' + author + '\n')
fid.write('''
#
# MOSSCO is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License v3+.  MOSSCO is distributed in the
# hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file
# LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms.
#

ifndef MOSSCO_DIR
export MOSSCO_DIR=$(subst /examples/generic$,,$(PWD))
endif

include $(MOSSCO_DIR)/src/Rules.make

''')

# Place conditionals for building this coupled system
conditionals = {'gotm' : 'GOTM', 'fabm' : 'FABM', 'erosed' : 'EROSED',
                'fabm_gotm' : 'GOTM_FABM', 'getm' : 'GETM'}
for item in componentSet.union(couplerSet):
    if conditionals.has_key(item):
        fid.write('ifneq ($(MOSSCO_' + conditionals[item] + '),true)\n')
        fid.write('$(error This example only works with MOSSCO_' + conditionals[item] + ' = true)\n')
        fid.write('endif\n')

libs = {'gotm'       : ['solver', 'gotm', 'gotm_prod', 'airsea_prod', 'meanflow_prod', 'seagrass_prod',
                   'output_prod', 'observations_prod', 'input_prod', 'turbulence_prod', 'util_prod'] ,
        'fabm_gotm'       : ['gotm', 'mossco_gotmfabm', 'solver', 'fabm_prod', 
                  'gotm', 'gotm_prod', 'airsea_prod', 'meanflow_prod', 'seagrass_prod',
                  'output_prod', 'observations_prod', 'input_prod', 'turbulence_prod', 'util_prod'],
        'fabm_sediment' : ['sediment', 'mossco_sediment', 'solver', 'fabm_prod'], 
        'constant'   : ['constant'],
        'clm_netcdf' : ['mossco_clm'],
        'benthos'    : ['mossco_benthos'],
        'erosed'     : ['erosed', 'mossco_erosed'],
        'simplewave' : ['mossco_simplewave'],
        'empty'      : ['empty'],
        'fabm0d'     : ['mossco_fabm0d', 'solver', 'airsea_prod', 
                        'input_prod', 'util_prod', 'fabm_prod']
}

deps = {'clm_netcdf' : ['libmossco_clm'],
        'benthos'    : ['libmossco_benthos'],
        'erosed'     : ['liberosed'],
        'fabm0d'     : ['libmossco_fabm0d'],
        'fabm0d'     : ['libmossco_fabm0d'],
        'fabmsediment' : ['libsediment'],
        'simplewave' : ['libmossco_simplewave'],
        'empty'      : ['libempty'],
        'constant'   : ['libconstant'],
        'gotm'       : ['libgotm', 'libsolver'],
        'fabm_gotm'       : ['libmossco_gotmfabm', 'libsolver', 'libgotm'] 
}

#fid.write('\nNC_LIBS += $(shell nf-config --flibs)\n\n')
fid.write('LDFLAGS += $(LIBRARY_PATHS)\n')
for item in componentSet.union(couplerSet):
    if libs.has_key(item):
        fid.write('LDFLAGS +=')
        if item=='gotm':
            fid.write(' -L$(GOTM_LIBRARY_PATH)')
        if item=='getm':
            fid.write(' -L$(GETM_LIBRARY_PATH)')
        if item=='fabm_sediment':
            fid.write(' -L$(FABM_LIBRARY_PATH)')
        if item=='fabm':
            fid.write(' -L$(FABM_LIBRARY_PATH) -L$(GOTM_LIBRARY_PATH)')
        if item=='fabm_gotm':
            fid.write(' -L$(FABM_LIBRARY_PATH) -L$(GOTM_LIBRARY_PATH)')
        if item=='fabm0d':
            fid.write(' -L$(FABM_LIBRARY_PATH) -L$(GOTM_LIBRARY_PATH)')
        for lib in libs[item]:
            fid.write(' -l' + lib)
        fid.write('\n')

fid.write('LDFLAGS += $(LIBS) -lmossco_util -lesmf $(ESMF_NETCDF_LIBS)  -llapack\n\n')

#for item in componentSet.union(couplerSet):
#    if libs.has_key(item):
#        if item=='gotm':
#            fid.write(' $(NC_LIBS)\n\n')
#        if item=='fabm_gotm':
#            fid.write(' $(NC_LIBS)\n\n')




fid.write('.PHONY: all exec\n\n')
fid.write('all: exec\n\n')
fid.write('exec: ' + coupling_name + '\n\n')
fid.write(coupling_name + ': toplevel_coupling.o main.o\n')
fid.write('\t$(F90) $(F90FLAGS) -o $@  $^ $(LDFLAGS)\n')
fid.write('\t@echo "Created example $(MOSSCO_DIR)/examples/generic/$@"\n')
fid.write('''
main.o: toplevel_coupling.o main.F90 libmossco_util
''')
fid.write('toplevel_coupling.o: toplevel_coupling.F90')
for item in componentSet.union(couplerSet):
    if deps.has_key(item):
        for dep in deps[item]:
            fid.write(' ' + dep)
fid.write('''

# Other subsidiary targets that might not be needed, these should evetually
# end up in some global Rules.make 

libmossco_gotmfabm libgotm:
	$(MAKE) -C $(MOSSCO_DIR)/src/components/gotm $@

libmossco_util:
	$(MAKE) -C $(MOSSCO_DIR)/src/utilities $@

libsediment libconstant libmossco_clm liberosed libmossco_fabm0d :
	$(MAKE) -C $(MOSSCO_DIR)/src/components $@

libempty libmossco_simplewave:
	$(MAKE) -C $(MOSSCO_DIR)/src/components $@

libmossco_sediment libsolver:
	$(MAKE) -C $(MOSSCO_DIR)/src/drivers $@

libsurfacescoupler libaocoupler:
	$(MAKE) -C $(MOSSCO_DIR)/src/mediators $@

libmossco_benthos:
	$(MAKE) -C $(MOSSCO_DIR)/src/components $@

libocean libatmosphere:
	$(MAKE) -C $(MOSSCO_DIR)/src/components/remtc $@

atmos.nc:
	@-ln -s /media/data/forcing/CLM/cDII.00.kss.2003.nc $@ || \
	ln -s /h/ksedata02/data/model/CLM/cDII.00.kss.2003.nc $@ || \
	echo "Could not find data file cDII.00.kss.2003.nc."

clean: extraclean
extraclean: 
	@-rm -f coupling toplevel_coupling.F90

''')
fid.close()



