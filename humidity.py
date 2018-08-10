#!/usr/bin/python -u

import os
import time
import urllib2
import threading

# http://pyserial.sourceforge.net/
import serial

server = "klatu"

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
    log("serial opened")
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

def monitor(dev):
    s = init_serial('/dev/' + dev)

    last = None

    while True:
        try:
            line = s.readline()
        except Exception, ex:
            print str(ex)
            time.sleep(10)
            s = init_serial()
            continue

        if not line.endswith("\r\n"):
            continue
        try:
            line = line.strip()
            parts = line.split(" ")
        except:
            continue

        if len(parts) != 2:
            continue

        now = time.time()
        if last:
            if (last + 30) > now:
                continue

        d = {
            "subtopic" : "humidity_0",
        }

        for part in parts:
            key, value = part.split('=', 1)
            d[key] = value
        log(d)

        last = now
        get(d)

#
#

serial_dev = "humidity_0"

base = '/dev'

devs = []

for name in os.listdir(base):
    if not name.startswith('humidity_'):
        continue
    log("found", name)
    devs.append(name)

threads = []

for dev in devs:
    thread = threading.Thread(target=monitor, args=(dev,))
    thread.start()
    threads.append(thread)

# FIN
