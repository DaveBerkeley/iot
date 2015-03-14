#!/usr/bin/python

import time
import os
import sys
import json
import optparse
import socket
import traceback

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

from broker import Broker

#   General home IoT data
#

def iot_handler(path, broker, data):
    topic = "home"
    try:
        jdata = json.loads(data)
        if jdata.get("pir") == "1":
            topic = "home/pir"
    except:
        pass
    broker.send(topic, data)

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

iot_dir = "/usr/local/data/iot"
rivers_dir = "/usr/local/data/rivers"
power_dir = "/usr/local/data/power"
solar_dir = "/usr/local/data/solar"
monitor_dir = "/usr/local/data/monitor"

handlers = {
    iot_dir : iot_handler,
    rivers_dir : rivers_handler,
    power_dir : power_handler,
    solar_dir : solar_handler,
    monitor_dir : monitor_handler,
}

paths = handlers.keys()

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
        handler = handlers[tree]
        handler(path, self.broker, data)

    def handle_file_change(self, path):
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
            f = open(path, "r")
            self.files[tree] = f

        if newfile and self.seek:
            f.seek(0, os.SEEK_END)

        # read all the pending changes
        while True:
            data = f.readline()
            if not data:
                break
            self.on_data(path, tree, data.strip())

    def dispatch(self, event):
        try:
            if event.event_type == "modified":
                path = event.src_path
                if path.endswith(".log"):
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
        tree = path[:-len("/yyyy/mm/dd.log")]
        assert handlers.get(tree)
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
        observer.schedule(event_handler, path, recursive=True)
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
