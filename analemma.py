#!/usr/bin/python

import datetime
import math
from subprocess import Popen, PIPE

import ephem

from solar_conf import lon, lat

def degrees(rad):
    #return rad
    return 180.0 * rad / math.pi

class Solar:

    def __init__(self, lat=None, lon=None):
        self.obs = ephem.Observer()
        self.obs.lat = lat
        self.obs.long = lon

    def sun(self, dt=None):
        self.obs.date = dt or datetime.datetime.now()
        sun = ephem.Sun()
        sun.compute(self.obs)
        return sun.alt, sun.az

#
#

s = Solar(lat, lon)

dt = datetime.datetime(2015, 1, 1, 12)
end = datetime.datetime(2016, 1, 1)
day = datetime.timedelta(days=1)

fmt = "%Y/%m/%d %H:%M"

ofile = open("/tmp/solar.csv", "w")

while dt < end:
    alt, az = [ degrees(x) for x in s.sun(dt) ]
    print >> ofile, dt.strftime(fmt), alt, az
    dt += day

args = [
    "set title 'Analemma'",
    "set xlabel 'azimuth'",
    "set ylabel 'altitude'",
    "set key off",
    "plot '/tmp/solar.csv' using 4:3"
]

cmd = "gnuplot --persist"

p = Popen(cmd, shell=True, stdin=PIPE).stdin
print p

for arg in args:
    print >> p, arg

# FIN
