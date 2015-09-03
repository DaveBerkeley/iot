#!/usr/bin/python -u

import time
import os
import sys
import json
import optparse
import socket
import traceback
import math
import datetime
import re

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

from broker import Broker

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

#   Dust sensor
#
#   Convert ratio of low to high signal to dust concentration.

def get_dust(ratio):
    percent = ratio * 100
    conc = 1.1 * math.pow(percent, 3)
    conc += -3.8 * math.pow(percent, 2)
    conc += 520 * percent 
    conc += 0.62
    return conc

dust_filter = Filter()

def dust_handler(ratio):
    conc = get_dust(ratio)
    now = datetime.datetime.now()
    dust_filter.add(conc, now)
    
    f_5 = dust_filter.filtered(datetime.timedelta(minutes=5))
    f_10 = dust_filter.filtered(datetime.timedelta(minutes=10))

    d = { 
        "dust" : conc,
        "dust_5" : f_5,
        "dust_10" : f_10,
        "ratio" : ratio,
    }
    return d

#
#

def node_handler(node, broker, data):
    try:
        jdata = json.loads(data)
    except ValueError:
        print "Error reading", data
        return
    #print "XX", node, broker, jdata

    for key, value in jdata.items():
        if key == "subtopic":
            continue
        topic = "node/" + str(node) + "/" + key
        print "\t", topic, value
        broker.send(topic, str(value))

#   General home IoT data
#

node_re = re.compile(".*_(\d+)")

def iot_handler(path, broker, data):
    topic = "home"
    try:
        jdata = json.loads(data)
        if jdata.get("pir") == "1":
            topic = "home/pir"
        if jdata.get("subtopic"):
            st = jdata["subtopic"]
            match =  node_re.match(st)
            if match:
                node = int(match.groups()[0])
                jdata["node"] = node
                node_handler("jeenet/%d" % node, broker, data)
            topic += "/" + st
        if jdata.get("dust"):
            jdata = dust_handler(float(jdata["dust"]))
            topic = "home/dust"
    except Exception, ex:
        print "ERROR", str(ex)
        return
    broker.send(topic, json.dumps(jdata))

#   River level monitor
#

def rivers_handler(path, broker, data):
    # 2015-03-12 20:46:18 tick
    # 2015-03-12 20:46:23 7267 'Kingston Bridge' 4.56

    parts = data.split()
    d = {}
    d["time"] = parts[0].replace("-", "/") + " " + parts[1]

    if parts[2] == "tick":
        d["id"] = "tick"
        topic = "rivers/tick"
    else:
        d["id"] = parts[2]
        name = " ".join(parts[3:-1])
        d["name"] = name[1:-1]
        d["level"] = float(parts[-1])
        topic = "rivers/level"

    broker.send(topic, json.dumps(d))

#   Smart meter : power usage
#

def power_handler(path, broker, data):
    # path: xxxx/yyyy/mm/dd.log
    # 230029 118.6
    parts = path.split("/")
    y, m, d = parts[-3], parts[-2], parts[-1][:2]
    hms, power = data.split()
    hms = ":".join([ hms[:2], hms[2:4], hms[4:] ])
    d = {
        "power" : float(power),
        "time" : "%s/%s/%s %s" % (y, m, d, hms),
    }
    broker.send("home/power", json.dumps(d))

#   Solar Power generation meter
#

def solar_handler(path, broker, data):
    # path: xxxx/yyyy/mm/dd.log
    # 16:53:42 9151773
    parts = path.split("/")
    y, m, d = parts[-3], parts[-2], parts[-1][:2]
    hms, power = data.split()
    d = {
        "power" : int(power, 10),
        "time" : "%s/%s/%s %s" % (y, m, d, hms),
    }
    broker.send("home/solar", json.dumps(d))

#
#   CPU / network monitoring for host

def monitor_handler(path, broker, data):
    # 07:27:02 0.14 0.14 0.09 772832 930861 35.0 31.0
    # hms load1, load2, load3 rx tx [ temp1 ... ]
    parts = path.split("/")
    y, m, d = parts[-3], parts[-2], parts[-1][:2]
    parts = data.split()
    d = {
        "time" : "%s/%s/%s %s" % (y, m, d, parts[0]),
        # CPU load
        "load_0" : parts[1],
        "load_1" : parts[2],
        "load_2" : parts[3],
        # Network
        "rx" : parts[4],
        "tx" : parts[5],
    }
    for i, temp in enumerate(parts[6:]):
        d["temp_%d" % i] = temp 

    host = socket.gethostname()
    d["host"] = host

    broker.send("home/net/" + host, json.dumps(d))

#
#

def gas_handler(path, broker, data):
    # /usr/local/data/gas/2015/06/29.log
    # '174831 58 0 0.00005' hhmmss sector rotations cubic_metres
    parts = path.split("/")
    y, m, d = parts[-3], parts[-2], parts[-1][:2]
    parts = data.split(" ")

    if len(parts) != 5:
        return

    hmd = parts[0]
    h, m, d = hmd[:2], hmd[2:4], hmd[4:]

    rots = int(parts[2])
    sector = int(parts[1])

    s = (64 - sector) / 64.0
    rots += s

    d = {
        "time" : "%s/%s/%s %s%s%s" % (y, m, d, h, m, d),
        "sector" : sector,
        "rots" : rots,
        "m3" : float(parts[3]),
        "rate" : float(parts[4]),
    }

    broker.send("home/gas", json.dumps(d))

    for key, value in d.items():
        broker.send("node/gas/" + key, value)
        

#
#

def syslog_handler(path, broker, data):
    # 'Apr 15 13:45:07 klatu dnsmasq-dhcp[2578]: DHCPACK(eth0) 192.168.0.139 1c:3e:84:62:5a:b7 chrubuntu'
    # 
    if path != "/var/log/syslog":
        return

    parts = data.split(" ")

    if len(parts) != 9:
        return
    if not "DHCPACK" in parts[5]:
        return

    ip, mac, host = parts[6:]

    d = {
        "ip" : ip,
        "mac" : mac,
        "host" : host,
    }
    broker.send("home/net/dhcp", json.dumps(d))

#
#

def weather_handler(path, broker, data):
    # /usr/local/data/weather/2015/06/29.log
    # json data
    broker.send("home/weather", json.dumps(data))

#
#

iot_dir = "/usr/local/data/iot"
rivers_dir = "/usr/local/data/rivers"
power_dir = "/usr/local/data/power"
solar_dir = "/usr/local/data/solar"
monitor_dir = "/usr/local/data/monitor"
gas_dir = "/usr/local/data/gas"
weather_dir = "/usr/local/data/weather"
syslog_dir = "/var/log"

handlers = {
    iot_dir : iot_handler,
    rivers_dir : rivers_handler,
    power_dir : power_handler,
    solar_dir : solar_handler,
    monitor_dir : monitor_handler,
    gas_dir : gas_handler,
    weather_dir : weather_handler,
    syslog_dir : None, # handled by syslog handler
}

paths = handlers.keys()

handlers["/var/log/syslog"] = syslog_handler

#
#

class Handler:

    def __init__(self, broker, seek):
        self.broker = broker
        self.files = {}
        for path in paths:
            self.files[path] = None
        self.seek = seek

    def on_data(self, path, tree, data):
        print tree, str(data)
        handler = handlers.get(tree)
        if handler is None:
            handler = handlers.get(path)
        if not handler:
            print "No handler for", path
            return
        handler(path, self.broker, data)

    def handle_file_change(self, path):
        if os.path.isdir(path):
            return

        tree = None
        for p in paths:
            if path.startswith(p):
                tree = p
                break

        f = self.files.get(tree)
        if not f is None:
            if f.name != path:
                self.files[tree] = None
                f = None

        newfile = False
        if f is None:
            newfile = True
            try:
                f = open(path, "r")
            except Exception, ex:
                print "Exception", str(ex)
                return
            self.files[tree] = f

        if newfile and self.seek:
            f.seek(0, os.SEEK_END)

        # read all the pending changes
        while True:
            data = f.readline()
            if not data:
                break
            print "on_data", path, `data`
            self.on_data(path, tree, data.strip())

    def dispatch(self, event):
        try:
            if event.event_type == "modified":
                path = event.src_path
                #if path.endswith("log"):
                self.handle_file_change(path)
        except Exception, ex:
            print "Exception", str(ex)
            traceback.print_exc()
            sys.exit(0) # TODO : remove me

#   Tail
#
#   Simulate watchdog events

import threading

class Tail:

    def __init__(self):
        self.path = None
        self.handler = None
        self.f = None
        self.thread = None
        self.dead = False

    def schedule(self, handler, path, *args, **kwargs):
        print path, handler
        assert self.path is None, "only one path allowed in Tail"
        self.path = path
        self.handler = handler
        # need to kludge global handlers
        # assuming yyyy/mm/dd.log
        if os.path.isdir(path):
            tree = path[:-len("/yyyy/mm/dd.log")]
        else:
            tree = path
        assert handlers.get(tree), (tree, path)
        handlers[path] = handlers[tree]

    def run(self):
        self.f = open(self.path, "r")
        self.f.seek(0, os.SEEK_END)
        while not self.dead:
            line = self.f.readline()
            if not line:
                time.sleep(0.1)
                continue
            class Event:
                pass
            event = Event()
            event.event_type = "modified"
            event.src_path = self.path
            self.handler.dispatch(event)

    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.dead = True

    def join(self):
        if self.thread:
            self.thread.join()

#
#

if __name__ == "__main__":

    p = optparse.OptionParser()
    p.add_option("-s", "--seek", dest="seek", action="store_true")
    p.add_option("-m", "--mqtt-server", dest="mqtt", default="mosquitto")
    p.add_option("-t", "--tail", dest="tail", action="store_true")

    opts, args = p.parse_args()    

    if len(args):
        paths = args

    if opts.tail:
        observer = Tail()
    else:
        observer = Observer()

    server = opts.mqtt
    print "connect to", server
    broker = Broker("watcher", server=server)
    broker.start()

    event_handler = Handler(broker, seek=opts.seek)

    for path in paths:
        print "monitor", path
        isdir = os.path.isdir(path)
        if path == "/var/log":
            isdir = False
        observer.schedule(event_handler, path, recursive=isdir)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        broker.stop()
        observer.stop()

    broker.join()
    observer.join()

# FIN
