#!/usr/bin/python

import time
import datetime
import json
import math

# https://pypi.python.org/pypi/pyephem
import ephem

from broker import Broker

# add your lat/lon in this config file :
from solar_conf import lat, lon

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

topic = "astro"

server = "mosquitto"
print "connect to", server
broker = Broker("solar", server=server)
broker.start()

print "Showing:",
for name in bodies:
    print name,
print

try:
    while True:
        now = datetime.datetime.utcnow()
        observer.date = now
        d = {
            "time" : str(ephem.Date(now)) + " UTC",
        }
        def degrees(x):
            return 180.0 * x / math.pi
        for name in bodies:
            alt, az = [ degrees(x) for x in body(name) ]
            d[name] = { "alt" : alt, "az" : az, }

        broker.send(topic, json.dumps(d))

        time.sleep(60)
except KeyboardInterrupt:
    broker.stop()

broker.join()

# FIN
