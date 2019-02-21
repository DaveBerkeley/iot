#!/usr/bin/env python3

import sys
import os
import json
import datetime
import argparse
from threading import Lock

#
#

#
#

log_lock = Lock()

def log(*args):
    with log_lock:
        now = datetime.datetime.now()
        ymd = now.strftime("%Y/%m/%d")
        hms = now.strftime("%H:%M:%S.%f")
        sys.stderr.write(ymd + " " + hms[:-3] + ' ')
        for arg in args:
            sys.stderr.write(str(arg) + ' ')
        sys.stderr.write("\n")

#
#

def find(base):
    paths = []
    for path, subdirs, files in os.walk(base):
        for name in files:
            if not name.endswith('.log'):
                continue
            p = os.path.join(path, name)
            paths.append(p)
    paths.sort()
    return paths

def tons(tt):
    # as nanosecond timestamp
    fmt = "%Y/%m/%d %H:%M:%S"
    dd = datetime.datetime.strptime(tt, fmt)
    return str(int(dd.timestamp())) + "000000000"

#
#

class Writer:

    def __init__(self, database, fname, lines):
        self.database = database
        self.fname = fname
        self.lines = lines
        self.idx = 0
        self.line = 0
        if fname:
            self.fopen()
        else:
            self.fout = sys.stdout

    def header(self):
        # write header
        self.write('# DDL')
        self.write('CREATE DATABASE ' + database)
        self.write('# DML')
        self.write('# CONTEXT-DATABASE: ' + database)
        self.write('')

    def fopen(self):

        self.line = 0
        path = self.fname % self.idx
        self.fout = open(path, "w")
        self.idx += 1
        self.header()

        log('writing to', path)

    def write(self, data):
        self.fout.write(data)
        self.fout.write('\n')

        if self.lines is None:
            return

        self.line += 1
        if self.line < self.lines:
            return

        self.fopen()
        
    def output(self, field, topic, value, tt):
        self.write("%s,src=%s %s=%s %s" % (field, topic, field, value, tons(tt)))

#
#   IoT files

voltage_dev = [ "vcc", "temp", "voltage" ]
humidity = [ "temp", "humidity" ]

devices = {
    "jeenet/gateway" : [ "temp" ],
    "jeenet/humiditydev_2" : [ "humidity", "temp", "vcc" ],
    "jeenet/voltagedev_6" : voltage_dev,
    "jeenet/voltagedev_7" : voltage_dev,    # bread maker
    "jeenet/voltagedev_8" : voltage_dev,
    "jeenet/voltagedev_9" : voltage_dev,    # porch
    "jeenet/voltagedev_10" : voltage_dev,
    "jeenet/voltagedev_11" : voltage_dev,   # car
    "jeenet/voltagedev_12" : voltage_dev,
    "humidity/0" : humidity,
    "humidity/1" : humidity,
    "humidity/2" : humidity,

    # not used yet, or obsolete
    "jeenet/kettle" : [ ],
    "jeenet/PIR" : [ ],
    "jeenet/Triac_4" : [ ],
    "jeenet/triac_4" : [ ],
    "jeenet/PirSensor_1" : [ ],
    "jeenet/pirsensor_1" : [ ],
    "jeenet/testdev_1" : [ ],
    "jeenet/testdev_2" : [ ],
    "jeenet/testdev_6" : [ ],
    "home/pressure" : [ ],
    "pressure" : [ ],
    "home/dust" : [ ],
    "dust" : [ ],
    "jeenet/testdev_1_1_6" : [ ],
    "jeenet/testdev_8" : [ ],
    "jeenet/relaydev_6" : [ ],
    "jeenet/relaydev_7" : [ ],
    "jeenet/relaydev_8" : [ ],
    "jeenet/relaydev_12" : [ ],
    "jeenet/relaydev_10" : [ ],
    "jeenet/magnetometerdev_12" : [ ],
    "jeenet/pulsedev_12" : [ ],
    "jeenet/pulsedev_1" : [ ],
    "humidity" : [ ],
    "humidity_0" : [ ],
    "humidity_1" : [ ],
}

node_lut = {
    # This is crap. The ipaddr (x.x.x.node) can change
    # Needs to be fixed to MAC address, and macaddr passed in.
    # These values checked 20-Feb-2019
    '209' : 'snoopie_04', # front room
    '165' : 'snoopie_05', # office
    '231' : 'snoopie_08', # back room -over rad
    '229' : 'snoopie_09', # bedroom
    '216' : 'snoopie_x1', # ??
}

def read_iot(writer, path):
    #print(path)
    for line in open(path):
        line = line.strip()
        try:
            d = json.loads(line)
        except:
            continue

        topic = d.get('subtopic')

        if topic and ('jeenet' in topic):
            # jeenet based radio devices
            fields = devices[topic]
            topic = topic.split('/')[-1]
        elif topic:
            fields = devices[topic]
            topic = topic.replace('/', '_')
        else:
            # wifi based devices
            ip = d.get('ipaddr')
            if ip is None:
                continue
            if len(d) == 2:
                # just ipaddr and time
                continue
            fields = []

            # skip obsolete / unwanted forms
            for field in [ "method", "key", "id", "text", "flash" ]:
                if d.get(field):
                    fields = None
                    break
            if fields is None:
                continue

            for field in [ "pir", "temp", "dust", "sea" ]:
                if not d.get(field) is None:
                    fields.append(field)

            assert fields, d
            # use the ip address: it is the only identifier
            node = ip.split('.')[-1]
            topic = node_lut.get(node)
            if not topic:
                log("no name for %s %s" % (node, type(node)))
                return

        tt = d['time']

        for field in fields:
            try:
                value = d.get(field)
                if value is None:
                    continue
                writer.output(field, topic, value, tt)
            except:
                print(d)
                raise

#
#

def parse_path(path):
    parts = path.split('/')
    parts[-1] = parts[-1].split('.')[0]
    y, m, d = parts[-3:]
    return y, m, d

def secs(tt):
    _, hms = tt.split(' ')
    h, m, s = hms.split(':')
    h, m, s = map(int, (h, m, s))
    return s + (60 * m) + (60 * 60 * h)

#   Solar Power
#

def read_solar(writer, path):
    y, m, d = parse_path(path)
    prev_tt = None
    last_total = None
    start_day = None
    for line in open(path):
        line = line.strip()
        hms, total = line.split()
        tt = "%s/%s/%s %s" % (y, m, d, hms)
        # meter reading : cumulative total
        writer.output("kwh", "solar", total, tt)

        # output diff since last tt as power
        if prev_tt and last_total:
            diff_Wh = int(total) - int(last_total)
            diff_secs = secs(tt) - secs(prev_tt)
            diff_h = diff_secs / (60 * 60.0)
            if diff_h:
                diff_W = diff_Wh / diff_h
                # instantaneous power output
                writer.output("power", "solar", diff_W, tt)

        # total so far today (each file is a new day)
        if not start_day is None:
            today = int(total) - int(start_day)
            # daily total
            writer.output("total", "solar", today, tt)

        if start_day is None:
            start_day = total
        last_total = total
        prev_tt = tt

#
#

def read_weather(writer, path):
    for line in open(path):
        line = line.strip()
        # the json seems to have been change to a Python print ..
        # so fix the quotes.
        line = line.replace("'", '"')
        try:
            d = json.loads(line)
        except:
            continue
        where = d['id'] # eg. 'Plymouth'
        src = d['src']  # 'owm'
        topic = src + '.' + where.lower()
        tt = d['time'] # 'yyyy/mm/dd hh:mm:ss'

        def out(key, fields, name, fn=None):
            if d.get(key):
                for field in fields:
                    value = d[key].get(field)
                    if not value is None:
                        txt = fn(name, field, topic)
                        writer.output(txt, topic, value, tt)

        def def_fn(name, field, topic):
            return name + field
        def rain_fn(name, field, topic):
            return "rain"

        out('main', [ 'temp', 'humidity', 'pressure' ], '', def_fn)
        out('wind', [ 'speed', 'deg' ], 'wind', def_fn)
        out('clouds', [ 'all' ], 'cloud', def_fn)
        out('rain', [ '3h' ], '', rain_fn)

#
#

def read_power(writer, path):
    yy, mm, dd = parse_path(path)
    for line in open(path):
        line = line.strip()

        hms, p = line.split(' ')
        h, m, s = hms[0:2], hms[2:4], hms[4:6]
        h, m, s = map(int, (h, m, s))
        tt = "%s/%s/%s %s:%s:%s" % (yy, mm, dd, h, m, s)

        writer.output('power', 'import', p, tt)

#
#

def read_gas(writer, path):
    # TODO
    yy, mm, dd = parse_path(path)
    for line in open(path):
        line = line.strip()
        print(line)

#
#

def read(writer, path, fn, ymd=None):
    paths = find(path)
    for p in paths:
        if ymd:
            yy, mm, dd = parse_path(p)
            if ymd > (yy, mm, dd):
                continue
        log(p)
        fn(writer, p)

#
#

if __name__ == "__main__":

    # ./influx.py --db iot --out data_%06d.txt --lines 1000000

    p = argparse.ArgumentParser(description='Read iot logs and format for influxdb import')
    p.add_argument('--db', dest='db')
    p.add_argument('--out', dest='out')
    p.add_argument('--lines', dest='lines', type=int, default=5000)
    p.add_argument('--ymd', dest='ymd')

    args = p.parse_args()

    assert args.db, 'must specify database'
    database = args.db

    writer = Writer(database, args.out, args.lines)

    # TODO : last n months?
    ymd = ('2019', '01', '01')

    read(writer, '/usr/local/data/weather', read_weather, ymd=ymd)
    read(writer, '/usr/local/data/solar',read_solar, ymd=ymd)
    read(writer, '/usr/local/data/iot', read_iot, ymd=ymd)
    read(writer, '/usr/local/data/power', read_power, ymd=ymd)

    #read(writer, '/usr/local/data/gas', read_gas, ymd=ymd)

# FIN
