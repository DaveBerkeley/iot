#!/usr/bin/env python3

import time
import datetime
import json
import os

# https://pypi.org/project/pyephem/
import ephem

import broker3

lat="50.3896"
lon="-4.1358"

class Solar:

    def __init__(self, lat=None, lon=None):
        self.obs = ephem.Observer()
        self.obs.lat = lat
        self.obs.long = lon

    def _fn(self, ctor, dt=None):
        self.obs.date = dt or datetime.datetime.now()
        body = ctor()
        body.compute(self.obs)
        return body

    def fn(self, ctor, dt=None):
        body = self._fn(ctor, dt)
        return { 'alt' : body.alt, 'az' : body.az }

    def sun(self, dt=None):
        return self.fn(ephem.Sun, dt)

    def moon(self, dt=None):
        body = self._fn(ephem.Moon, dt)
        return { 'alt' : body.alt, 'az' : body.az, 'phase' : body.moon_phase }

    def venus(self, dt=None):
        return self.fn(ephem.Venus, dt)

    def mars(self, dt=None):
        return self.fn(ephem.Mars, dt)

    def jupiter(self, dt=None):
        return self.fn(ephem.Jupiter, dt)

    def saturn(self, dt=None):
        return self.fn(ephem.Saturn, dt)

    def mercury(self, dt=None):
        return self.fn(ephem.Mercury, dt)

#
#

while True:
    
    now = datetime.datetime.now()
    s = Solar(lat=lat, lon=lon)

    d = {
        'sun' : s.sun(),
        'moon' : s.moon(),
        'mercury' : s.mercury(),
        'mars' : s.mars(),
        'venus' : s.venus(),
        'jupiter' : s.jupiter(),
        'saturn' : s.saturn(),
        'time' : now.strftime('%Y/%m/%d %H:%M:%S'),
        'z' : 'local',
    }

    text = json.dumps(d)

    _id = "celest_%d" % os.getpid()
    broker = broker3.Broker(_id, server="mosquitto")
    broker.send("home/celest", text)

    time.sleep(60)

# FIN
