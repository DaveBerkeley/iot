#!/usr/bin/python -u

import os
import time
import urllib2
import threading

# http://pyserial.sourceforge.net/
import serial

server = "klatu"

dead = False

period = 30

#
#

lock = threading.Lock()

def log(*args):
    with lock:
        print time.strftime("%y/%m/%d %H:%M:%S :"), 
        for arg in args:
            print arg,
        print

#
#

def init_serial(path):
    log("open serial '%s'" % path)
    s = serial.Serial(path, baudrate=9600, timeout=1, rtscts=True)
    log("serial opened", path)
    return s

#
#

def get(data):
    url = "http://%s/wiki/iot.cgp?" % server
    args = []
    for key, value in data.items():
        args.append("%s=%s" % (key, value))

    url += "&".join(args)
    urllib2.urlopen(url)

#
#

def monitor(name, dev):
    path = '/dev/' + name
    s = init_serial(path)

    changes = 0
    last_state = None

    while not dead:
        try:
            line = s.readline()
        except Exception, ex:
            log("exception", str(ex))
            time.sleep(10)
            s = init_serial(path)
            continue

        if not line.endswith("\r\n"):
            continue
        try:
            line = line.strip()
            parts = line.split(" ")
        except:
            log("exception", str(ex))

        if len(parts) != 2:
            log(parts)
            continue

        milis, state = parts

        if state != last_state:
            changes += 1
            last_state = state

        d = {
            "subtopic" : "water/%s" % dev,
            "dev" : dev,            
            "state" : state,
            "changes" : changes,
        }

        log(d)
        get(d)

#
#

# assumes /dev/water
monitor("water", 0)

# FIN
