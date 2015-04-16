#!/usr/bin/python

import time
import datetime

# https://pypi.python.org/pypi/pyephem
import ephem

from broker import Broker

# add your lat/lon in this config file :
from solar_config import lat, lon

#
#

observer = ephem.Observer()
observer.lat = lat
observer.long = lon

bodies = [
    "Sun",
    "Moon",
    #"Mercury",
    #"Venus",
    #"Mars",
    #"Jupiter",
    #"Saturn",
]

def body(name):
    obj = getattr(ephem, name)()
    obj.compute(observer)
    return obj.alt, obj.az

while True:
    now = datetime.datetime.now()
    observer.date = now
    d = {
        "time" : now.strftime("%Y/%m/%d %H:%M:%S"),
    }
    for name in bodies:
        alt, az = [ float(x) for x in body(name) ]
        d[name] = { "alt" : alt, "az" : az, }
    print d

    time.sleep(60)

# FIN
