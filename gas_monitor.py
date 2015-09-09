#!/usr/bin/python -u

import time
import datetime
import optparse
import os

import serial

#
#

def log(*args):
    print time.strftime("%Y/%m/%d %H:%M:%S"),
    for arg in args:
        print arg,
    print

#
#   Filter out noise
#
#   Expect data in sequence eg. 5, 4, 3, 2, 1, 0, sectors-1, sectors-2, ..
#
#   Remove noise and allow small holes in the sequence.

class Filter:

    def __init__(self, sectors):
        self.sectors = sectors
        self.data = None
        self.value = None
        self.prev_value = None

    def prev(self, n, r=5):
        for i in range(1, r):
            p = (i + n) % self.sectors
            yield p

    def add(self, data):
        if data != self.prev_value:
            log(data)
            self.prev_value = data

        self.data = data

        if self.value:
            if data in self.prev(self.value):
                return

        self.value = data

    def get(self):
        return self.value

#
#

tfile = None

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
#   Average

class Average:
    def __init__(self):
        self.data = []
    def add(self, now, value):
        self.data.append((now, value))
        # remove old data
        dt = datetime.timedelta(minutes=1)
        while self.data:
            t, v = self.data[0]
            if (t + dt) > now:
                break
            del self.data[0]
    def diff(self):
        at, a = self.data[0]
        bt, b = self.data[-1]
        dv = b - a
        dt = (bt - at).total_seconds()
        dt * 3600
        if not dt:
            return 0
        return dv / dt

average = Average()

#
#

def save_to_log(f, hm, value, rotations, rot, av):
    log(hm, value, rotations, rot)
    print >> f, hm, value, rotations, "%.5f" % rot, av
    f.flush()

#
#

if __name__ == "__main__":

    feet3_2_meters3 = 0.0283168466
    parkinson_cowen = 0.017
    rot = parkinson_cowen * feet3_2_meters3

    p = optparse.OptionParser()
    p.add_option("-d", "--dev", dest="dev", default="/dev/gasmeter")
    p.add_option("-b", "--base", dest="base", default="/usr/local/data/gas")
    #p.add_option("-b", "--base", dest="base", default="/tmp/gas")
    p.add_option("-s", "--sectors", dest="sectors", default=64)
    p.add_option("-r", "--rotation", dest="rotation", default=rot)
    p.add_option("-i", "--index", dest="index", type="int", default=0)
    opts, args = p.parse_args()

    s = None
    last_sector = None
    f = None
    filt = Filter(opts.sectors)
    rotations = opts.index
    last_diff = None
    next_t = None

    def parse(line):
        line = line.strip()
        return int(line)

    while True:

        line = get_line(opts)

        if not line:
            time.sleep(1)
            continue

        try:
            sector = parse(line)
        except ValueError:
            continue

        if sector == -1: # bad frame
            continue

        filt.add(sector)
        value = filt.get()
        #print sector, value
        if value is None:
            continue

        now = datetime.datetime.now()
        ymd = now.strftime("%Y/%m/%d.log")
        hm = now.strftime("%H%M%S")
        path = os.path.join(opts.base, ymd)

        if f and (f.name != path):
            f = None

        dirname, x = os.path.split(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
            f = None
            last_sector = None

        if f is None:
            log("make", path)
            f = file(path, "a")

        # log any changes, check for rotations
        if value != last_sector:
            if not last_sector is None:
                margin = 4
                if value > (opts.sectors - margin):
                    if last_sector < margin:
                        rotations += 1

        this_rot = (1.0 - (value / float(opts.sectors))) * opts.rotation
        rot = this_rot + (rotations * opts.rotation)
        average.add(now, rot)

        logit = False
        diff = average.diff()

        if next_t is None:
            next_t = now + datetime.timedelta(minutes=1, seconds=1)

        if now > next_t:
            next_t = None
            logit = True

        if value != last_sector:
            logit = True

        if logit:
            #if value != last_sector:
            next_t = now + datetime.timedelta(minutes=1, seconds=1)
            last_sector = value
            save_to_log(f, hm, value, rotations, rot, diff)

# FIN
