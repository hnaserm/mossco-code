# This Makefile snippet is part of MOSSCO; definition of MOSSCO-wide make rules
# 
# Copyright (C) 2013 Carsten Lemmen, Helmholtz-Zentrum Geesthacht
#
# MOSSCO is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License v3+.  MOSSCO is distributed in the 
# hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file 
# LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms. 
#


# 1. Checking that we're using GNU make 
#    Of course, this command already requires gmake, so a better solution is required here
ifeq ($(shell make --version | grep -c GNU),0)
$(error GNU make is required)
endif 

# More useful output from Make and count of iterations of Rules.make
OLD_SHELL := $(SHELL)
SHELL = $(warning Building $@$(if $<, (from $<))$(if $?, ($? newer)))$(OLD_SHELL)

export COUNT ?= 0
COUNT := $(shell expr $(COUNT) + 1)
$(warning $(COUNT))

# 2. Importing all FABM-related environment variables and checking that the environment is sane
#    At the moment, we require that MOSSCO_FABMDIR, FABMHOST, and FORTRAN_COMPILER are set and that
#    the fabm library is installed in the production version (libfabm_prod)
# 
ifeq ($(COUNT),1)
MOSSCO_FABM=false

ifndef MOSSCO_FABMDIR
external_FABMDIR = $(MOSSCO_DIR)/external/fabm-git
ifneq ($(wildcard $(external_FABMDIR)/src/Makefile),)
export MOSSCO_FABMDIR=$(external_FABMDIR)
endif
endif

ifdef MOSSCO_FABMDIR
export FABMDIR=$(MOSSCO_FABMDIR)
MOSSCO_FABM=true
else
ifdef FABMDIR
MOSSCO_FABM=true
ifeq ($(COUNT),1)
$(warning Assuming you have a working FABM in ${FABMDIR}, proceed at your own risk or set the environment variable $$MOSSCO_FABMDIR explicitly to enable the build system to take  care of the FABM build) 
endif
endif
endif

export MOSSCO_FABM

ifeq ($(MOSSCO_FABM),true)

#!> @todo remove FABMHOST here and move it to makefiles where FABM is remade
ifndef FABMHOST
export FABMHOST=mossco
ifeq ($(COUNT),1)
$(warning FABMHOST set to FABMHOST=mossco)
endif
endif

ifndef FORTRAN_COMPILER
FABM_AVAILABLE_COMPILERS=$(shell ls -1 $(FABMDIR)/compilers/compiler.* | cut -d'.' -f2)
FABM_AVAILABLE_COMPILERS:=$(patsubst %compiler.,,$(FABM_AVAILABLE_COMPILERS))
$(error FORTRAN_COMPILER needs to be set to one of the compilers in $(FABMDIR)/compilers: $(FABM_AVAILABLE_COMPILERS))
endif

FABM_MODULE_PATH=$(FABMDIR)/modules/$(FABMHOST)/$(FORTRAN_COMPILER)
FABM_INCLUDE_PATH=$(FABMDIR)/include
FABM_LIBRARY_PATH=$(FABMDIR)/lib/$(FABMHOST)/$(FORTRAN_COMPILER)

endif

# 3. (optional) Importing all GOTM-related environment variables and checking that the environment is sane
# At the moment, we require that GOTMDIR, FABM, and FORTRAN_COMPILER are set and that
# the gotm library is installed in the production version (libgotm_prod)

MOSSCO_GOTM=false

ifndef MOSSCO_GOTMDIR
external_GOTMDIR = $(MOSSCO_DIR)/external/gotm-git
ifneq ($(wildcard $(external_GOTMDIR)/src/Makefile),)
export MOSSCO_GOTMDIR=$(external_GOTMDIR)
endif
endif

ifdef MOSSCO_GOTMDIR
export GOTMDIR=$(MOSSCO_GOTMDIR)
MOSSCO_GOTM=true
else
ifdef GOTMDIR
MOSSCO_GOTM=true
ifeq ($(COUNT),1)
$(warning Assuming you have a working GOTM in ${GOTMDIR}, proceed at your own risk or set the environment variable $$MOSSCO_GOTMDIR explicitly to enable the build system to take  care of the GOTM build) 
endif
endif
endif

ifdef GOTMDIR
MOSSCO_GOTM=true
endif

export MOSSCO_GOTM

ifeq ($(MOSSCO_GOTM),true)

GOTM_MODULE_PATH=$(GOTMDIR)/modules/$(FORTRAN_COMPILER)
GOTM_INCLUDE_PATH=$(GOTMDIR)/include
GOTM_LIBRARY_PATH=$(GOTMDIR)/lib/$(FORTRAN_COMPILER)

endif


# 4. ESMF stuff, only if ESMFMKFILE is declared.  We need to work on an intelligent system that prevents
#    the components and mediators to be built if ESMF is not found in your system
#
ifndef ESMFMKFILE
ifndef MOSSCO_ESMF
$(error Compiling without ESMF support. Comment this line 90 in Rules.make if you want to proceed)
export MOSSCO_ESMF=false
endif
else
include $(ESMFMKFILE)
export MOSSCO_ESMF=true
ifdef ESMF_DIR
MOSSCO_OS=$(shell $(ESMF_DIR)/scripts/esmf_os)
else
MOSSCO_OS=$(shell uname -s)
endif
ifneq ("x$(ESMF_NETCDF)","x")
export MOSSCO_NETCDF_LIBPATH=$(ESMF_NETCDF_LIBPATH)
endif
export MOSSCO_OS
endif

## 5. EROSED
MOSSCO_EROSED=false

ifndef EROSED_DIR
external_EROSED_DIR = $(MOSSCO_DIR)/external/erosed-svn
ifneq ($(wildcard $(external_EROSED_DIR)),)
export EROSED_DIR=$(external_EROSED_DIR)
endif
endif

ifdef EROSED_DIR
MOSSCO_EROSED=true
endif

export MOSSCO_EROSED

# 6. MOSSCO declarations. The MOSSCO_DIR and the build prefix are set, as well as the bin/mod/lib paths relative
#    to the PREFIX
#
ifndef MOSSCO_DIR
ifdef MOSSCODIR
MOSSCO_DIR=$(MOSSCODIR)
else
MOSSCO_DIR=$(subst /src$,,$(PWD))
endif
endif
export MOSSCO_DIR

ifeq ($(wildcard $(MOSSCO_DIR)),) 
$(error the directory MOSSCO_DIR=$(MOSSCO_DIR) does not exist)
endif

ifdef PREFIX
MOSSCO_PREFIX=$(PREFIX)
else
MOSSCO_PREFIX=$(MOSSCO_DIR)
endif
export MOSSCO_PREFIX

export MOSSCO_MODULE_PATH=$(MOSSCO_PREFIX)/modules/$(FORTRAN_COMPILER)
export MOSSCO_LIBRARY_PATH=$(MOSSCO_PREFIX)/lib/$(FORTRAN_COMPILER)
export MOSSCO_BIN_PATH=$(MOSSCO_PREFIX)/bin

# 7. Putting everything together.  This section could need some cleanup, but does work for now
#

# determine the compiler used by FABM
ifeq (${MOSSCO_FABM},true)
FABM_F90COMPILER=$(shell grep 'FC=' $(FABMDIR)/compilers/compiler.$(FORTRAN_COMPILER) | cut -d"=" -f2)
FABM_F90COMPILER_VERSION:=$(shell $(FABM_F90COMPILER) --version | head -1)
endif

ifndef F90
ifdef ESMF_F90COMPILER
export F90=$(ESMF_F90COMPILER)
F90_VERSION:=$(shell $(F90) --version | head -1)
$(warning F90 automatically determined from ESMF_F90COMPILER variable: F90=$(F90))
else
export F90=$(shell grep 'FC=' $(FABMDIR)/compilers/compiler.$(FORTRAN_COMPILER) | cut -d"=" -f2)
F90_VERSION:=$(shell $(F90) --version | head -1)
$(warning F90 automatically determined from FABM environment: F90=$(F90))
endif
endif

ifneq ($(F90_VERSION),$(FABM_F90COMPILER_VERSION))
MPICH_F90COMPILER=$(shell $(F90) -compile_info 2> /dev/null | cut -d' ' -f1)
#MPICH_F90COMPILER_VERSION:=$(shell $(MPICH_F90COMPILER) --version | head -1)
ifneq ($(MPICH_F90COMPILER_VERSION),$(FABM_F90COMPILER_VERSION))
ifndef MOSSCO_COMPILER
$(warning F90=$(F90) different from compiler used by FABM ($(FABM_F90COMPILER)))
endif
endif
endif
export MOSSCO_COMPILER=$(F90)
export F90
export F90_VERSION
export FABM_F90COMPILER_VERSION
export MPICH_F90COMPILER_VERSION

ifeq ($(MOSSCO_FABM),true)
INCLUDES  = -I$(FABM_INCLUDE_PATH) -I$(FABM_MODULE_PATH) -I$(FABMDIR)/src/drivers/$(FABMHOST)
endif
INCLUDES += $(ESMF_F90COMPILEPATHS)
INCLUDES += -I$(MOSSCO_MODULE_PATH)
ifeq ($(MOSSCO_GOTM),true)
INCLUDES += -I$(GOTM_MODULE_PATH)
endif


#!> @todo expand existing F90FLAGS var but check for not duplicating the -J entry
ifeq ($(FORTRAN_COMPILER),GFORTRAN)
F90FLAGS = -J$(MOSSCO_MODULE_PATH)
EXTRA_CPP=
else
ifeq ($(FORTRAN_COMPILER),IFORT)
F90FLAGS = -module $(MOSSCO_MODULE_PATH)
EXTRA_CPP= -stand f03
endif
endif
export F90FLAGS

ifndef HAVE_LD_FORCE_LOAD
HAVE_LD_FORCE_LOAD=$(shell ld -v 2>&1 | grep -c LLVM)
ifeq ($(HAVE_LD_FORCE_LOAD),1)
HAVE_LD_FORCE_LOAD=true
else
HAVE_LD_FORCE_LOAD=false
endif
export HAVE_LD_FORCE_LOAD
endif 

LIBRARY_PATHS += $(ESMF_F90LINKPATHS) $(ESMF_F90LINKRPATHS) 
LIBRARY_PATHS += -L$(MOSSCO_LIBRARY_PATH)
ifneq ($(MOSSCO_NETCDF_LIBPATH),)
LIBRARY_PATHS += -L$(MOSSCO_NETCDF_LIBPATH)
endif
export LIBRARY_PATHS

LIBS += $(ESMF_F90LINKLIBS)
LIBS += $(MOSSCO_NETCDF_LIBS)
export LIBS

export CPPFLAGS = $(DEFINES) $(EXTRA_CPP) $(INCLUDES) $(ESMF_F90COMPILECPPFLAGS) -I.

LDFLAGS += $(ESMF_F90LINKOPTS)
LDFLAGS += $(LIBRARY_PATHS)
export LDFLAGS
endif

# Make targets
.PHONY: default all clean doc info prefix libfabm_external libgotm_external

default: prefix all

clean:
	@rm -f *.o *.mod

distclean: clean
	@rm -f *.swp

prefix:
	@mkdir -p $(MOSSCO_LIBRARY_PATH)
	@mkdir -p $(MOSSCO_MODULE_PATH)
	@mkdir -p $(MOSSCO_BIN_PATH)

info:
	@echo SHELL = $(SHELL)
	@echo MAKE = $(MAKE)
	@echo HAVE_LD_FORCE_LOAD = $(HAVE_LD_FORCE_LOAD)
	@echo INCDIRS = $(INCDIRS)
	@echo CPPFLAGS = $(CPPFLAGS)
	@echo LDFLAGS = $(LDFLAGS)
	@echo LIBS = $(LIBS)
	@echo LINKDIRS = $(LINKDIRS)
	@echo FORTRAN_COMPILER = $(FORTRAN_COMPILER)
	@env | grep ^F90 | sort 
ifeq ($(MOSSCO_FABM),true)
	@env | grep ^FABM | sort 
endif
ifeq ($(MOSSCO_GOTM),true)
	@env | grep ^GOTM | sort 
endif
	@env | grep ^MOSSCO_ | sort 


# External libraries

libfabm_external: 
ifdef MOSSCO_FABMDIR
ifeq  ($(wildcard $(FABM_LIBRARY_PATH)/libfabm_prod.a),)
	@echo Recreating the FABM library in $(FABM_LIBRARY_PATH)
	(export FABM_F2003=true ; $(MAKE) -C $(FABMDIR)/src)
endif
endif

# KK-TODO: think about compiling gotm without updating its exe
libgotm_external:
ifdef MOSSCO_GOTMDIR
ifeq ($(MOSSCO_GOTM_FABM),true)
ifdef MOSSCO_FABMDIR
ifeq  ($(wildcard $(FABMDIR)/lib/gotm/$(FORTRAN_COMPILER)/libfabm_prod.a),)
	@echo Recreating the FABM library in $(FABMDIR)/lib/gotm/$(FORTRAN_COMPILER)
	(export FABM_F2003=true ; $(MAKE) -C $(FABMDIR)/src gotm)
endif
endif
ifeq  ($(wildcard $(GOTMDIR)/lib/$(FORTRAN_COMPILER)/libgotm_prod.a),)
	@echo Recreating the GOTM library in $(GOTM_LIBRARY_PATH)
	(export FABM=true ; export FABM_F2003=true ; $(MAKE) -C $(GOTMDIR)/src)
endif
else
ifeq  ($(wildcard $(GOTMDIR)/lib/$(FORTRAN_COMPILER)/libgotm_prod.a),)
	@echo Recreating the GOTM library without FABM in $(GOTM_LIBRARY_PATH)
	(unset FABM ; $(MAKE) -C $(GOTMDIR)/src)
endif
endif
endif


# Common rules
#ifndef EXTRA_CPP

%.o: %.F90
	@echo "Compiling $<"
	$(F90) $(CPPFLAGS) $(F90FLAGS) -c $< -o $@	
%.o: %.f90
	@echo "Compiling $<"
	$(F90) $(CPPFLAGS) $(F90FLAGS) -c $< -o $@
%.mod: %.f90
	@echo "Compiling $<"
	$(F90) $(CPPFLAGS) $(F90FLAGS) -c $< -o $@
#%.o: %.f90
#	@echo "Compiling $<"
#	$(F90) $(CPPFLAGS)  -c $< -o $@
#else
#%.f90: %.F90
#	$(CPP) $(CPPFLAGS) $< -o $@
#	$(F90_to_f90)
#%.o: %.f90
#	$(F90) $(F90FLAGS) $(EXTRA_FFLAGS) -c $< -o $@
#endif
