from pylab import *
import netCDF4
import sys,os
import numpy
from scipy.interpolate import interp1d

if len(sys.argv)<3:
  print('  usage: mossco2zax.py mossco_output.nc variable1,variable2,..')
  exit()

ncfile = sys.argv[1]
variables = sys.argv[2].split(',')

zaxname='zax'
depthname = 'water_depth_at_soil_surface'
fillvalue = -9999.
vardtype = 'f4'

# ------------

nc = netCDF4.Dataset(ncfile,'a')
ncv = nc.variables

if depthname in ncv.keys():
  depth = squeeze(ncv[depthname][:])

if zaxname not in ncv.keys():
  zlevels = array([0.0,5.0,10.0,20.0,30.0,40.0,50.0,75.0,100.0,150.,200.0,250.0])
  nc.createDimension(zaxname,len(zlevels))
  v = nc.createVariable(zaxname,'f4',(zaxname,))
  v.units = 'm'
  v.positive = 'down'
  v[:] = zlevels
  nc.sync()
else:
  zlevels = ncv[zaxname][:]
zaxnum = len(zlevels)

tnum,znum,ynum,xnum = ncv[variables[0]].shape

# create fields of fill values
varz = fillvalue*ones((zaxnum,ynum,xnum),dtype=vardtype)
for var in variables:
  if var+'_z' in ncv.keys():
    if not(ncv[var+'_z'].shape == (tnum,zaxnum,ynum,xnum)):
      print('shape of existing variable %s does not match shape of interpolated fields'%(var+'_z'))
      exit()
  else:
    dims = ncv[var].dimensions
    newdims = (dims[0],zaxname,dims[2],dims[3])
    coords = ncv[var].coordinates.split()
    v = nc.createVariable(var+'_z',vardtype,newdims)
    v.units = ncv[var].units
    v.long_name = ncv[var].long_name
    v.standard_name = ncv[var].standard_name
    v.missing_value = fillvalue
    v.coordinates = zaxname+' '+coords[1]+' '+coords[2]

#create 3d zlevels array
zlevels3d = zeros((zaxnum,ynum,xnum))
for z in range(zaxnum):
  zlevels3d[z] = -zlevels[z] * ones((ynum,xnum))

# so far assume sigma coordinates
for t in range(tnum):
  print('  timestep %d'%t)
  h = numpy.tile(depth[t]/znum,(znum,1,1))
  z = cumsum(h,axis=0)-0.5*h - numpy.tile(depth[t],(znum,1,1))
  for varname in variables:
    #ncv[varname+'_z'][t] = interp1d(z,ncv[varname][t],axis=0)(-zlevels3d)
    for j in range(ynum):
      for i in range(xnum):
        varz[:,j,i] = interp(-zlevels,squeeze(z[:,j,i]),squeeze(ncv[varname][t,:,j,i]))
    ncv[varname+'_z'][t]=varz
  nc.sync()

nc.close()

