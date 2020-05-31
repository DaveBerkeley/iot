#!/usr/bin/env python3

import time
import datetime
import json
import os
import argparse
import urllib

# https://pypi.org/project/pyephem/
import ephem

import broker3

ISS = 'https://www.celestrak.com/NORAD/elements/stations.txt'

#
#

def log(*args):
    now = datetime.datetime.now()
    print(now, '', end='')
    for arg in args:
        print(arg, end='')
    print()

#
#

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

def get_iss(url, lat, lon):
    req = urllib.request.urlopen(url)
    if req.getcode() != 200:
        log("error reading", url)
        return

    data = req.read()
    data = data.decode('utf-8')

    lines = data.split('\r\n')
    found = []
    for line in lines:
        line = line.strip()
        if line == 'ISS (ZARYA)':
            found.append(line)
            continue
        if found:
            found.append(line)
            if len(found) == 3:
                break

    def iss():
        return ephem.readtle(*found)
  
    solar = Solar(lat=lat, lon=lon)
    return solar.fn(iss)

#
#

class TestBroker:
    def send(self, *args):
        log(args)

#
#

if __name__ == '__main__':

    p = argparse.ArgumentParser(description='Generate celestial data')
    p.add_argument('--test', dest='test', action='store_true')
    p.add_argument('--iss', dest='iss', action='store_true')
    p.add_argument('--period', dest='period', type=int, default=60)
    p.add_argument('--mqtt', dest='mqtt', default='mosquitto')
    p.add_argument('--lat', dest='lat', type=float, default=50.3896)
    p.add_argument('--lon', dest='lon', type=float, default=-4.1358)

    args = p.parse_args()

    #
    #

    if args.test:
        broker = TestBroker()
    else:
        _id = "celest_%d" % os.getpid()
        broker = broker3.Broker(_id, server=args.server)

    #
    #

    while True:
 
        now = datetime.datetime.now()
        s = Solar(lat=args.lat, lon=args.lon)

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

        if args.iss:
            try:
                d['iss'] = get_iss(ISS, args.lat, args.lon)
            except Exception as ex:
                log("Error", str(ex))

        text = json.dumps(d)
        broker.send("home/celest", text)

        time.sleep(args.period)

# FIN
