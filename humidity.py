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

    last = None

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
            continue

        if len(parts) != 2:
            continue

        now = time.time()
        if last:
            if (last + period) > now:
                continue

        d = {
            "subtopic" : "humidity",
            "dev" : dev,
        }

        for part in parts:
            key, value = part.split('=', 1)
            d[key] = value
        log(d)

        last = now
        get(d)

#
#

base = '/dev'

devs = []

for name in os.listdir(base):
    if not name.startswith('humidity_'):
        continue
    dev = name[len("humidity_"):]
    log("found", name)
    devs.append((name, dev))

threads = []

for name, dev in devs:

    def fn(name, dev):
        try:
            monitor(name, dev)
        except KeyboardInterrupt as ex:
            log("exception", str(ex))
            global dead
            dead = True
    thread = threading.Thread(target=fn, args=(name, dev,))
    thread.start()
    threads.append(thread)

try:
    for thread in threads:
        thread.join()
except KeyboardInterrupt as ex:
    log("exception", str(ex))
    dead = True

# FIN
