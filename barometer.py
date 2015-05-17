#!/usr/bin/python -u

import time
import urllib2

# http://pyserial.sourceforge.net/
import serial

serial_dev = "/dev/nano"
server = "klatu"

#
#

def log(*args):
    print time.strftime("%y/%m/%d %H:%M:%S :"), 
    for arg in args:
        print arg,
    print

#
#

def init_serial():
    log("open serial '%s'" % serial_dev)
    s = serial.Serial(serial_dev, baudrate=9600, timeout=1, rtscts=True)
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

s = init_serial()

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
        parts = line.split(",")
    except:
        continue
    if len(parts) != 8:
        continue

    d = {
        "subtopic" : "pressure",
    }
    for i in range(0, len(parts), 2):
        key, value = parts[i:i+2]
        d[key] = value
    log(line)
    get(d)

# FIN
