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
#   Remove forward movement
#   Remove reverse movement > 10

class Filter:

    def __init__(self, sectors):
        self.sectors = sectors
        self.data = None
        self.last = []
        self.value = None

    def prev(self, n, r=3):
        for i in range(1, r):
            p = (i + n) % self.sectors
            yield p

    def add(self, data):
        log(data)
        self.data = data

        if self.value:
            if data in self.prev(self.value):
                return

        self.value = data

        self.last = self.last[-1:] + [ data, ]
        log(self.last)

    def get(self):
        return self.value

    #def rotation(self):
    #    # detect rotations
    #    r = self.rot
    #    self.rot = False
    #    return r

#
#

tfile = None

def get_line(opts):

    if opts.test:
        global tfile
        if tfile is None:
            tfile = open(opts.test)
        f = tfile

        while True:
            line = f.readline()
            parts = line.strip().split()
            if len(parts) == 3:
                return parts[2]

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
#

if __name__ == "__main__":

    feet3_2_meters3 = 0.0283168466
    parkinson_cowen = 0.017
    rot = parkinson_cowen * feet3_2_meters3

    p = optparse.OptionParser()
    p.add_option("-d", "--dev", dest="dev", default="/dev/gasmeter")
    #p.add_option("-b", "--base", dest="base", default="/usr/local/data/gas")
    p.add_option("-b", "--base", dest="base", default="/tmp/gas")
    p.add_option("-s", "--sectors", dest="sectors", default=64)
    p.add_option("-r", "--rotation", dest="rotation", default=rot)
    p.add_option("-t", "--test", dest="test")
    opts, args = p.parse_args()

    s = None
    last_sector = None
    last_time = datetime.datetime.now()
    f = None
    filt = Filter(opts.sectors)
    rotations = 0

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
        filtered = filt.get()
        #print sector, filtered
        if filtered is None:
            continue

        #if filt.rotation():
        #    rotations += 1

        now = datetime.datetime.now()
        ymd = now.strftime("%Y/%m/%d.log")
        hm = now.strftime("%H%M%S")
        path = os.path.join(opts.base, ymd)

        dirname, x = os.path.split(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
            f = None
            last_sector = None

        if f is None:
            log("make", path)
            f = file(path, "a")

        if filtered != last_sector:
            last_sector = filtered
            this_rot = (filtered / float(opts.sectors)) * opts.rotation
            rot = this_rot + (rotations * opts.rotation)
            log(hm, filtered, rotations, rot)
            print >> f, hm, filtered, rotations, "%.5f" % rot
            f.flush()

# FIN
