#!/usr/bin/python -u

import os
import time
import urllib2
import threading
import datetime

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

var_path = '/var/lib/water_meter/counter.txt'

def get_counter(path=var_path):
    try:
        data = open(path).read()
        c = float(data)
        return c
    except IOError:
        log(path, "not found")
        return 0

def set_counter(value, path=var_path):
    f = open(path, "w")
    f.write("%.4f" % value)
    f.close()

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

    changes = get_counter()
    last_state = None

    def ordinal():
        dt = datetime.date.today()
        return dt.toordinal()

    today = ordinal()
    today_total = 0

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

        # one rotation is 10 litres
        # ie. 0.01 of a cubic metre
        # so each count (roughly) is 0.005
        increment = 0.005

        if state != last_state:
            if not last_state is None:
                changes += increment
                today_total += increment
            last_state = state
            set_counter(changes)

        if ordinal() != today:
            today_total = 0;
            today = ordinal()

        d = {
            "subtopic" : "water/%s" % dev,
            "dev" : dev,            
            "state" : state,
            "today" : today_total,
            "changes" : changes,
        }

        log(d)
        get(d)

#
#

# assumes /dev/water
monitor("water", 0)

# FIN
