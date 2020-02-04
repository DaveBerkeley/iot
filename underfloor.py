#!/usr/bin/python -u

import os
import time
import threading
import json
import argparse
import urllib2

# http://pyserial.sourceforge.net/
import serial

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

def get(server, data):
    url = "http://%s/wiki/iot.cgp?" % server
    args = []
    for key, value in data.items():
        args.append("%s=%s" % (key, value))

    url += "&".join(args)
    urllib2.urlopen(url)

#
#

def init_serial(path):
    log("open serial '%s'" % path)
    s = serial.Serial(path, baudrate=9600, timeout=1, rtscts=True)
    log("serial opened", path)
    return s

#
#

class Underfloor:

    lut = { 
        'd' : 'distance',
        'h' : 'humidity',
        't' : 'temp',
    }

    def __init__(self, path, server, topic, period=9):
        self.dead = False
        self.path = path
        self.s = init_serial(self.path)
        self.data = {}
        self.idx = 0
        self.period = period
        self.last = None
        self.last_time = 0
        self.topic = topic
        self.server = server

    def parse(self, line):
        d = {}
        d.update(self.data)
        parts = line.split()
        for part in parts:
            key, value = part.split('=')
            d[self.lut[key]] = float(value)

        self.idx += 1
        if self.idx >= self.period:
            self.idx = 0

        self.data.update(d)
        return d

    def monitor(self):
        while not self.dead:
            try:
                line = self.s.readline()
            except Exception, ex:
                log("exception", str(ex))
                time.sleep(10)
                self.s = init_serial(self.path)
                continue

            if not line:
                continue

            log(line.strip())

            try:
                d = self.parse(line)
            except Exception as ex:
                log("exception", str(ex))
                continue

            d['subtopic'] = self.topic

            now = time.time()
            if d == self.last:
                if (self.last_time + self.period) > now:
                    continue

            self.last_time = now
            self.last = d

            get(self.server, d)

#
#

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Interface underfloor nano')
    parser.add_argument('--dev', dest='dev', default='/dev/underfloor')
    parser.add_argument('--topic', dest='topic', default='underfloor/0')
    parser.add_argument('--server', dest='server', default='mosquitto')

    args = parser.parse_args()

    usb = Underfloor(args.dev, args.server, args.topic)

    try:
        usb.monitor()
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        log("exception", str(ex))

# FIN
