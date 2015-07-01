#!/usr/bin/python -u

import time
import urllib2

# http://pyserial.sourceforge.net/
import serial

#
#

def log(*args):
    print time.strftime("%Y/%m/%d %H:%M:%S"),
    for arg in args:
        print arg,
    print

#
#

def put(opts, data):
    url = "http://%s/wiki/iot.cgp?" % opts.server
    args = []
    for key, value in data.items():
        args.append("%s=%s" % (key, value))

    url += "&".join(args)
    urllib2.urlopen(url)
#
#

def get_line(opts):
    global s
    if s is None:
        s = serial.Serial(opts.dev, 9600)

    try:
        return s.readline()
    except:
        s = None
        time.sleep(5)
        return None

s = None

class O:
    pass

opts = O()

opts.dev = "/dev/nano_2-1_2"
opts.server = "klatu"

while True:
    d = get_line(opts)
    parts = d.strip().split(",")
    print parts
    conc = float(parts[2])
    d = { 
        "dust" : conc,
        "subtopic" : "home/dust",
    }
    log(conc)
    put(opts, d)

# FIN
