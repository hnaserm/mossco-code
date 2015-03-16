#!/bin/bash
#
# This script  is part of MOSSCO.  It tailors big netcdf files to relevant eco-variables
#
# @copyright (C) 2015 Helmholtz-Zentrum Geesthacht
# @author Kai W. Wirtz
# @author Carsten Lemmen
#
# MOSSCO is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License v3+.  MOSSCO is distributed in the
# hope that it will be useful, but WITHOUT ANY WARRANTY.  Consult the file
# LICENSE.GPL or www.gnu.org/licenses/gpl-3.0.txt for the full license terms.
#

# ---------------------
# User configuration
# Declare a list of variables to extract
declare -a vn=("phytoplankton_in_water" "nutrients_in_water" "zooplankton_in_water" "surface_downwelling_photosynthetic_radiative_flux")

model=''      # Fabm model name, e.g. hzg_maecs
outdir=cut    # Where to put the extracted files
prefix=netcdf_out  # Prefix of files to process
dt=2          # slicing of time dimension
dlat=2        # slicing of lat dimension
dlon=1        # slicing of lon dimension
# ---------------------
# Needs number of processors  as argument

if [[ "x$1" == "x" ]] ; then
  echo "This script needs the number of processors as input argument."
  echo "Provide 0 if you do not want to process multiprocessor output."
  exit 1
else
  nproc=$(expr $1 - 1)
fi

mkdir -p $outdir

# build comma separated string
ts=$model${vn[0]}
for (( i=1; i<${#vn[@]}; i++ )) do
  ts=$ts','$model${vn[$i]}
done # i

if [[ $nproc == -1 ]]; then
  fname=${prefix}'.nc'
  if ! test -f $fname ; then
    echo "File $fname does not exist"
    exit 1
  fi
  outname='cut/'${prefix}'_cut.nc'
  echo $fname '->' $outname
  # invokes nco tool and writes output to folder "cut/"
  #   skipping every 2nd lateral grid point and output-time step
  ncks -O -v time,getmGrid2D_getm_lat,getmGrid2D_getm_lon,getmGrid3D_getm_lat,getmGrid3D_getm_lon,$ts\
    -d getmGrid2D_getm_1,1,,${dlon} \
    -d getmGrid2D_getm_2,1,,${dlat} \
    -d getmGrid3D_getm_1,1,,${dlon} \
    -d getmGrid3D_getm_2,1,,${dlat} \
    -d time,1,,${dt} $fname $outname

  # compares file sizes
  ls -l  $fname $outname
else
	# loop over all nc files generated by mossco for multiprocessor output
	for p in $(seq -f "%02g" 0 $nproc); do
		fname='netcdf_out.'$p.'nc'
    if ! [[ -f $fname ]] ; then
      echo "File $fname does not exist"
      exit 1
    fi
		outname='cut/'${prefix}'_cut_'$p'.nc'
		echo $fname '->' $outname
		# invokes nco tool and writes output to folder "cut/"
		ncks -O -v time,getmGrid2D_getm_lat,getmGrid2D_getm_lon,getmGrid3D_getm_lat,getmGrid3D_getm_lon,$ts\
			-d getmGrid2D_getm_1,1,,${dlon} \
			-d getmGrid2D_getm_2,1,,${dlat} \
			-d getmGrid3D_getm_1,1,,${dlon} \
			-d getmGrid3D_getm_2,1,,${dlat} \
			-d time,1,,${dt} $fname $outname
		ls -l  $fname $outname
	done
fi