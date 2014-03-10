import yaml
import sys
import os

if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
     filename = '1d_reference.yaml'
     #filename = 'constant_constant_constant.yaml'

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

dependencyList=[]

if config.has_key('dependencies'):
    dependencies = config.pop('dependencies');    

componentList=[]
intervals =[]
directions = []
couplingList=[]
couplerList=[]
  
coupling = config.pop("coupling")


for item in coupling:
    if type(item) is dict:
        if item.has_key("components"):
            componentList.extend([item["components"][0], item["components"][-1]])
            couplingList.append(item["components"])
            componentList.extend([item["components"][0], item["components"][-1]])
            n=len(item["components"])
            if n==2:
                couplerList.append("copy_coupler")
            for i in range(1,n-1):
                couplerList.append(item["components"][i])    
            if item.has_key("interval"):
                intervals.append(item["interval"])
            else:
                intervals.append("60 min")
            if item.has_key("direction"):
                directions.append(item["direction"])
    else:
        print 'Warning, dictionary expected for item ' + item

componentSet=set(componentList)
componentList=list(componentSet)
couplerSet=set(couplerList)
couplerList=list(couplerSet)

# Set a default coupling alarm interval of 6 minutes
if len(intervals) == 0:
    intervals=len(couplerList) * ['6 m']

# if there are any dependencies specified, go through the list of components
# and sort this list
for component in componentList:
    for item in dependencies:
        if item.has_key(component):
          compdeps = item.values()[0]
          if type(compdeps) is list:
              for compdep in compdeps:
                 if componentList.index(component)< componentList.index(compdep):
                   c=componentList.pop(componentList.index(compdep))
                   componentList.insert(componentList.index(component),c) 
          elif componentList.index(component)< componentList.index(compdeps):
              c=componentList.pop(componentList.index(compdeps))
              componentList.insert(componentList.index(component),c)
#if componentList.index(component)>componentList.index(dep)
#    

print componentList, couplerList

# Done parsing the list, now write the new toplevel_component file
       
outfilename = 'toplevel_component.F90'
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

fid.write('module ' + 'toplevel_component\n') 
fid.write('''
  use esmf
  use mossco_variable_types
  use mossco_state\n
''')

for item in componentList:
    fid.write('  use ' + item + '_component, only : ' + item + '_SetServices => SetServices \n')
for item in couplerList:
    fid.write('  use ' + item + ', only : ' + item + '_SetServices => SetServices \n')

fid.write('\n  implicit none\n\n  private\n\n  public SetServices\n')
fid.write('''
  type(ESMF_GridComp),dimension(:),save, allocatable :: gridCompList
  type(ESMF_CplComp),dimension(:), save, allocatable :: cplCompList
  type(ESMF_State), dimension(:),  save, allocatable :: exportStates, importStates
  type(ESMF_Alarm), dimension(:),  save, allocatable :: cplAlarmList
  character(len=ESMF_MAXSTR), dimension(:), save, allocatable :: gridCompNames
  character(len=ESMF_MAXSTR), dimension(:), save, allocatable :: cplCompNames
  character(len=ESMF_MAXSTR), dimension(:), save, allocatable :: cplNames
''')

for item in couplerList:
    fid.write('  type(ESMF_CplComp), save  :: ' + item + 'Comp\n')    
for item in componentList:
    fid.write('  type(ESMF_GridComp), save :: ' + item + 'Comp\n')    
for item in componentList:
    fid.write('  type(ESMF_State), save    :: ' + item + 'ExportState, ' + item + 'ImportState\n')    

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
    character(ESMF_MAXSTR) :: name, message
    type(ESMF_Alarm)       :: childAlarm
    type(ESMF_Clock)       :: childClock
    type(ESMF_Clock)       :: clock !> This component's internal clock
    logical                :: clockIsPresent
     
    rc = ESMF_SUCCESS
     
    !! Check whether there is already a clock (it might have been set 
    !! with a prior ESMF_gridCompCreate() call.  If not, then create 
    !! a local clock as a clone of the parent clock, and associate it
    !! with this component.  Finally, set the name of the local clock
    call ESMF_GridCompGet(gridComp, name=name, clockIsPresent=clockIsPresent, rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    if (clockIsPresent) then
      call ESMF_GridCompGet(gridComp, clock=clock, rc=rc)     
    else
      clock = ESMF_ClockCreate(parentClock, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      call ESMF_GridCompSet(gridComp, clock=clock, rc=rc)    
    endif
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    call ESMF_ClockSet(clock, name=trim(name)//' clock', rc=rc)
    if(rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    
    !! Log the call to this function
    call ESMF_ClockGet(clock, currTime=currTime, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    call ESMF_TimeGet(currTime,timeStringISOFrac=timestring)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
    write(message,'(A)') trim(timestring)//' '//trim(name)//' initializing ...'
    call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)

    !! Allocate the fields for all gridded components and their names
''')
fid.write('    numGridComp = ' + str(len(componentList)) )
fid.write('''
    allocate(gridCompList(numGridComp))
    allocate(gridCompNames(numGridComp))
    allocate(importStates(numGridComp))
    allocate(exportStates(numGridComp))
    
''')
for i in range(0, len(componentList)):
    fid.write('    gridCompNames(' + str(i+1) + ') = \'' + componentList[i] + '\'\n') 
    
fid.write('''
    !! Create all gridded components, and create import and export states for these
    do i = 1, numGridComp
      gridCompList(i) = ESMF_GridCompCreate(name=trim(gridCompNames(i))//'Comp', rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      exportStates(i) = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_UNSPECIFIED, &
        name=trim(gridCompNames(i))//'ExportState')
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
      importStates(i) = ESMF_StateCreate(stateintent=ESMF_STATEINTENT_UNSPECIFIED, &
        name=trim(gridCompNames(i))//'ImportState')
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
    enddo
   
    !! Now register all setServices routines and initialize the gridded components
''')

for i in range(0, len(componentList)):
    fid.write('    call ESMF_GridCompSetServices(gridCompList(' + str(i+1) + '), ' + componentList[i] + '_SetServices, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')

fid.write('''
    do i=1,numGridComp
      call ESMF_GridCompInitialize(gridCompList(i), importState=importStates(i), &
      exportState=exportStates(i), clock=clock, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
    enddo
    
''')

if len(couplerList)>0:
    fid.write('    !! Allocate the fields for all coupler components and their names\n')
    fid.write('    numCplComp = ' + str(len(couplerList)) )
    fid.write('''
    allocate(cplCompList(numCplComp))
    allocate(cplCompNames(numCplComp))
''')

for i in range(0, len(couplerList)):
    fid.write('    cplCompNames(' + str(i+1) + ') = \'' + couplerList[i] + '\'\n') 
fid.write('''    
    do i = 1, numCplComp
      cplCompList(i) = ESMF_CplCompCreate(name=trim(cplCompNames(i))//'Comp', rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
    enddo
    
''')
for i in range(0,len(couplerList)):
    fid.write('    call ESMF_CplCompSetServices(cplCompList(' + str(i+1) + '), ' + couplerList[i] + '_SetServices, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n\n')

for i in range(0,len(couplingList)):
    item=couplingList[i]
    if len(item) != 3:
        continue
    ifrom = componentList.index(item[0])
    ito   = componentList.index(item[2])
    icpl  = couplerList.index(item[1])
    
    fid.write('    call ESMF_CplCompInitialize(cplCompList(' + str(icpl+1) + '), importState=importStates(' + str(ito+1) + '), &\n')
    fid.write('      exportState=exportStates(' + str(ifrom+1) + '), clock=clock, rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n\n')
 
fid.write('    numCplAlarm = ' + str(len(couplingList)))
fid.write('''
    if (.not.allocated(cplAlarmList)) allocate(cplAlarmList(numCplAlarm))
    if (.not.allocated(cplNames)) allocate(cplNames(numCplAlarm))
    do i=1, numCplAlarm 
      cplNames(i)='copy'    
    enddo
    !! Set the coupling alarm starting from start time of local clock
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
    fid.write('    call ESMF_TimeIntervalSet(alarmInterval, startTime, ' + unit + '=' + number + ' ,rc=rc)\n')
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
    !! Set the default ringTime to the stopTime of local clock, then get all Alarms
    !! from local clock into alarmList, find those that contain the string "cplAlarm"
    !! and look for the earliest ringtime in all coupling alarms.  Save that in the
    !! ringTime
    call ESMF_ClockGet(clock, stopTime=ringTime, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc) 
       
    call ESMF_ClockGetAlarmList(clock,ESMF_ALARMLIST_ALL,alarmCount=alarmCount,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    if (.not.allocated(alarmList)) allocate(alarmList(alarmCount))
    call ESMF_ClockGetAlarmList(clock,ESMF_ALARMLIST_ALL,alarmList=alarmList,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    do i=1,ubound(alarmList,1)
      call ESMF_AlarmGet(alarmList(i), ringTime=time, name=name, rc=rc)
      
      call ESMF_TimeGet(time,timeStringISOFrac=timestring)
      write(message,'(A)') trim(name)//' rings at '//trim(timestring)
      call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)
      
      if (index(trim(name),'cplAlarm') < 1) cycle 
      if (time<ringTime) ringTime=time    
    enddo
    if (allocated(alarmList)) deallocate(alarmList)
    
    !! Set the timestep such that it corresponds to the time until the 
    !! first ringing alarm, log that time
    call ESMF_ClockGet(clock,currTime=currTime,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    call ESMF_ClockSet(clock,timeStep=ringTime-currTime,rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
      
    call ESMF_GridCompGet(gridComp, name=name, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

    call ESMF_TimeGet(ringTime,timeStringISOFrac=timestring, rc=rc)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
    write(message,'(A)') trim(name)//' alarms ring next at '//trim(timestring)
    call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)
    
    !! Log the successful completion of this function
    call ESMF_TimeGet(currTime,timeStringISOFrac=timestring)
    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
    write(message,'(A)') trim(timestring)//' '//trim(name)//' initialized'
    call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)

  end subroutine Initialize

  subroutine Run(gridComp, importState, exportState, parentClock, rc)

    type(ESMF_GridComp)  :: gridComp
    type(ESMF_State)     :: importState, exportState
    type(ESMF_Clock)     :: parentClock
    integer, intent(out) :: rc

    character(len=ESMF_MAXSTR) :: timestring, cplName
    type(ESMF_Time)            :: stopTime, currTime, ringTime, time
    type(ESMF_TimeInterval)    :: timeInterval, ringInterval
    integer(ESMF_KIND_I8)      :: advanceCount,  i, j, k, l
    integer(ESMF_KIND_I4)      :: alarmCount, petCount, localPet
    integer(ESMF_KIND_I4)      :: numGridComp, numCplComp, hours
    
    type(ESMF_Alarm), dimension(:), allocatable :: alarmList
    type(ESMF_Alarm)        :: childAlarm
    type(ESMF_Clock)        :: childClock, clock
    logical                 :: clockIsPresent
    type(ESMF_State)        :: impState, expState
    type(ESMF_Field)        :: field
    type(ESMF_FieldBundle)  :: fieldBundle
    type(ESMF_Array)        :: array
    type(ESMF_ArrayBundle)  :: arrayBundle
    type(ESMF_StateItem_Flag), dimension(:), allocatable :: itemTypeList
    character(len=ESMF_MAXSTR), dimension(:), allocatable:: itemNameList
    integer                  :: itemCount
    
    character(len=ESMF_MAXSTR) :: message, compName, name, alarmName, otherName   
    
    if (.not.allocated(alarmList)) allocate(alarmList(20))

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
      !! same time as my own clock's currTime, if yes, then run the respective couplers
      !! or simply copy all fields
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
        if (time>currTime) cycle

        !! Find all the alarms in this child and call all the couplers that
        !! have ringing alarms at this stage
   
        call ESMF_ClockGetAlarmList(childClock, alarmListFlag=ESMF_ALARMLIST_ALL, &
          alarmCount=alarmCount, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

        if (alarmCount>ubound(alarmList,1)) then
          deallocate(alarmList)
          allocate(alarmList(alarmCount))
        endif
        
        if (alarmCount==0) then
          call ESMF_LogWrite('No alarm found in '//trim(compName), ESMF_LOGMSG_WARNING)
          timeInterval=stopTime-currTime
        else                 
          call ESMF_ClockGetAlarmList(childClock, alarmListFlag=ESMF_ALARMLIST_ALL, &
             alarmList=alarmList, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
        endif
        
        do j=1,alarmCount
          call ESMF_AlarmGet(alarmList(j), name=alarmName, ringTime=ringTime, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
  
          !! Skip this alarm if it is not a cplAlarm
          if (index(trim(alarmName),'cplAlarm') < 1) cycle
  
          !! Skip this alarm if it is inbound of this component
          if (trim(alarmName(1:index(alarmName,'--')-1))/=trim(compName(1:index(compName,'Comp')-1))) cycle
            
          !! Skip this alarm if it is not ringing now
          !if (ringTime > currTime) cycle
            
          call ESMF_TimeGet(ringTime,timeStringISOFrac=timeString)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
          
          write(message,'(A)') trim(compName)//' '//trim(alarmName)//' rings at '//trim(timeString)
          call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)
            
          compName=trim(alarmName(1:index(alarmName,'--')-1))
          otherName=trim(alarmName(index(alarmName,'--')+2:index(alarmName,'--cplAlarm')-1))
          
          do l=1,ubound(cplAlarmList,1) 
            if (cplAlarmList(l) == alarmList(j)) then
              cplName = trim(cplNames(l))
              exit
            endif
          enddo
            
          write(message,'(A)') trim(timeString)//' '//trim(compName)//' ->'
          if (trim(cplName) /= 'copy') then
            write(message,'(A)') trim(message)//' '//trim(cplName)//' ->'
          else
            write(message,'(A)') trim(message)//' ('//trim(cplName)//') ->'
          endif
          write(message,'(A)') trim(message)//' '//trim(otherName)  
          call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)            
            
          !! for now, transmit all Fields from my export state into the import state of the other component
          call ESMF_GridCompGet(gridCompList(i), exportState=expState, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

          write(*,*) i,j,k,l
          !! Search the gridCompList for other's name
          do k=1, ubound(gridCompList,1)
              call ESMF_GridCompGet(gridCompList(k), name=name, rc=rc)
              if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
              
              if (trim(name)==trim(otherName)//'Comp') exit
          enddo

          write(*,*) i,j,k,l

          if (trim(name) /= trim(otherName)//'Comp') then
            write(message,'(A)') 'Did not find component '//trim(otherName)
            call ESMF_LogWrite(trim(message), ESMF_LOGMSG_ERROR)  
            call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)          
          endif
          
          write(*,*) i,j,k,l

          call ESMF_GridCompGet(gridCompList(k), importState=impState, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
          
          call ESMF_TimeGet(currTime,timeStringISOFrac=timeString)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
          write(message,'(A)') trim(timeString)//' Calling '//trim(cplCompNames(l))
          call ESMF_LogWrite(trim(message), ESMF_LOGMSG_INFO)  
          
          call ESMF_CplCompRun(cplCompList(l), importState=impState, exportState=expState, clock=clock, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
          
        enddo 
      enddo


      !! Loop through all components and check whether their clock is currently at the 
      !! same time as my own clock's currTime, if yes, then run the component
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

        if (time>currTime) cycle
        
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
        endif

        !! Set the default ringTime to the stopTime of local clock, then get all Alarms
        !! from local clock into alarmList, find those that contain the string "cplAlarm"
        !! and look for the earliest ringtime in all coupling alarms.  Save that in the
        !! ringTime
        call ESMF_ClockGet(clock, stopTime=ringTime, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc) 
                
        do j=1,alarmCount
          call ESMF_AlarmGet(alarmList(j), name=alarmName, ringTime=time, &
            ringInterval=ringInterval, rc=rc)
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)
          if (index(trim(alarmName),'cplAlarm')<1) cycle
        
          if (time==currTime) ringTime=currTime+ringInterval
          if (time<ringTime) ringTime=time
        enddo 

        timeInterval=ringTime-currTime
        
        call ESMF_ClockSet(childClock, stopTime=ringTime, rc=rc) 
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)

        call ESMF_TimeIntervalGet(timeInterval, h=hours, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
        
        write(message,'(A,A,G6.2,A)') trim(timeString)//' calling '//trim(compName), &
          ' to run for ', hours, ' h'
        call ESMF_LogWrite(trim(message),ESMF_LOGMSG_INFO, rc=rc);
        
        call ESMF_GridCompRun(gridCompList(i),importState=importStates(i),&
          exportState=exportStates(i), clock=clock, rc=rc)
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
        
        call ESMF_ClockGet(childClock, currTime=time, rc=rc) 
        if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
        
        if (time == currTime) then
          !! This child component did not advance its clock in its Run() routine
          !! We do that here
          call ESMF_ClockAdvance(childClock, timeStep=timeInterval, rc=rc) 
          if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)
        endif
      enddo

      !! Now that all child components have been started, find out the minimum time
      !! to the next coupling and use this as a time step for my own clock Advance
      call ESMF_GridCompGet(gridComp, name=name, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)      
      
      call ESMF_ClockGetAlarmList(clock, alarmListFlag=ESMF_ALARMLIST_ALL, &
        alarmCount=alarmCount, rc=rc)
      if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT, rc=rc)

      if (alarmCount==0) then
        call ESMF_LogWrite('No alarm not found in '//trim(name), ESMF_LOGMSG_WARNING)
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
for item in componentList:
    fid.write('    call ESMF_GridCompDestroy(gridCompList(' + str(i+1) + '), rc=rc)\n')
    fid.write('    if (rc /= ESMF_SUCCESS) call ESMF_Finalize(endflag=ESMF_END_ABORT)\n')
    i += 1
i=0
for item in couplerList:
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

end module toplevel_component
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
        'netcdf'     : ['mossco_netcdf'],
        'simplewave' : ['mossco_simplewave'],
        'empty'      : ['empty'],
        'fabm0d'     : ['mossco_fabm0d', 'solver', 'airsea_prod', 
                        'input_prod', 'util_prod', 'fabm_prod'],
        'pelagic_benthic_coupler' : ['pelagicbenthiccoupler'],
        'benthic_pelagic_coupler' : ['pelagicbenthiccoupler'],
        'copy_coupler' : ['copycoupler']
}

deps = {'clm_netcdf' : ['libmossco_clm'],
        'benthos'    : ['libmossco_benthos'],
        'erosed'     : ['liberosed'],
        'fabm0d'     : ['libmossco_fabm0d'],
        'fabm0d'     : ['libmossco_fabm0d'],
        'fabm_sediment' : ['libsediment', 'libmossco_sediment', 'libsolver'],
        'simplewave' : ['libmossco_simplewave'],
        'netcdf'      : ['libmossco_netcdf'],
        'empty'      : ['libempty'],
        'constant'   : ['libconstant'],
        'gotm'       : ['libgotm', 'libsolver'],
        'fabm_gotm'       : ['libmossco_gotmfabm', 'libsolver', 'libgotm'],
        'pelagic_benthic_coupler' : ['libpelagicbenthiccoupler'],
        'benthic_pelagic_coupler' : ['libpelagicbenthiccoupler'],
        'copy_coupler' : ['libcopycoupler']
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

#fid.write('LDFLAGS += $(LIBS) -lmossco_util -lesmf $(ESMF_NETCDF_LIBS)  -llapack\n\n')
fid.write('LDFLAGS += $(LIBS) -lmossco_util -lesmf $(ESMF_NETCDF_LIBS) \n\n')

#for item in componentSet.union(couplerSet):
#    if libs.has_key(item):
#        if item=='gotm':
#            fid.write(' $(NC_LIBS)\n\n')
#        if item=='fabm_gotm':
#            fid.write(' $(NC_LIBS)\n\n')




fid.write('.PHONY: all exec coupling\n\n')
fid.write('all: exec\n\n')
fid.write('exec: libmossco_util ')
for item in componentSet.union(couplerSet):
    if deps.has_key(item):
        for dep in deps[item]:
            fid.write(' ' + dep)
fid.write(' ' + coupling_name + '\n\n')
fid.write(coupling_name + ': toplevel_component.o ../common/main.o\n')
fid.write('\t$(F90) $(F90FLAGS) -o $@  $^ $(LDFLAGS)\n')
fid.write('\t@echo "Created example $(MOSSCO_DIR)/examples/generic/$@"\n')
fid.write('toplevel_component.o : toplevel_component.F90')
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

libempty libmossco_simplewave libmossco_netcdf:
	$(MAKE) -C $(MOSSCO_DIR)/src/components $@

libmossco_sediment libsolver:
	$(MAKE) -C $(MOSSCO_DIR)/src/drivers $@

libsurfacescoupler libaocoupler:
	$(MAKE) -C $(MOSSCO_DIR)/src/mediators $@

libmossco_benthos:
	$(MAKE) -C $(MOSSCO_DIR)/src/components $@

libocean libatmosphere:
	$(MAKE) -C $(MOSSCO_DIR)/src/components/remtc $@

libcopycoupler:
	$(MAKE) -C $(MOSSCO_DIR)/src/mediators libcopycoupler
 
libpelagicbenthiccoupler:
	$(MAKE) -C $(MOSSCO_DIR)/src/mediators pelagicbenthiccoupler benthicpelagiccoupler
 
atmos.nc:
	@-ln -s /media/data/forcing/CLM/cDII.00.kss.2003.nc $@ || \
	ln -s /h/ksedata02/data/model/CLM/cDII.00.kss.2003.nc $@ || \
	echo "Could not find data file cDII.00.kss.2003.nc."

clean: extraclean
extraclean: 
	@-rm -f coupling

''')
fid.close()



