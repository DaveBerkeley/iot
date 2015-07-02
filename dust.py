#!/usr/bin/python -u

import time
import datetime
import urllib2
import optparse

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
    url = "http://%s/wiki/iot.cgp?" % opts.mqtt
    args = []
    for key, value in data.items():
        args.append("%s=%s" % (key, value))

    url += "&".join(args)
    try:
        urllib2.urlopen(url)
    except Exception, ex:
        log(str(ex))
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

#
#   Filter

class Filter:

    def __init__(self, dt=datetime.timedelta(minutes=10)):
        self.data = []
        self.dt = dt

    def add(self, value, dt):
        self.data.append((dt, value))
        while self.data:
            t, v = self.data[0]
            if t > (dt - self.dt):
                break
            del self.data[0]

    def filtered(self, dt):
        now, _ = self.data[-1]
        total = 0.0
        count = 0
        for t, v in self.data:
            if t < (now - dt):
                continue
            total += v
            count += 1
        return total / float(count)

#
#

s = None

if __name__ == "__main__":

    serial_dev = "/dev/dust"

    p = optparse.OptionParser()
    p.add_option("-d", "--dev", dest="dev", type="str", default=serial_dev)
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    opts, args = p.parse_args()

    f = Filter()

    while True:
        d = get_line(opts)
        parts = d.strip().split(",")
        print parts
        conc = float(parts[2])
        
        now = datetime.datetime.now()
        f.add(conc, now)
        
        f_5 = f.filtered(datetime.timedelta(minutes=5))
        f_10 = f.filtered(datetime.timedelta(minutes=10))

        d = { 
            "dust" : conc,
            "dust_5" : f_5,
            "dust_10" : f_10,
            "subtopic" : "dust",
        }
        log(conc)
        put(opts, d)

# FIN
