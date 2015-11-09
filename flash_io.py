#!/usr/bin/python

import sys
import json
import time
import optparse
import Queue

import jsonrpclib

from jeenet.system.core import DeviceProxy
import broker

#
#

next_rid = 0

def make_rid():
    global next_rid
    next_rid += 1
    return next_rid & 0xFF

#
#

class Checker:
    def __init__(self, x):
        pass

#
#   Decouple MQTT messages from the reader thread

class MqttReader:

    def __init__(self):
        self.q = Queue.Queue()
    def add(self, ident, info):
        #print ident, info
        self.q.put((ident, info))
    def on_device(self, x):
        data = json.loads(x.payload)
        f = data.get("flash")
        if f:
            self.add("D", f)
    def on_gateway(self, x):
        data = json.loads(x.payload)
        p = data.get("packets")
        if p:
            self.add("G", p)
    def pop(self, timeout=0.1):
        try:
            return self.q.get(True, timeout)
        except Queue.Empty:
            return None

#
#

class Scheduler:

    def __init__(self):
        self.q = []

    def add(self, t, fn):
        t += time.time()
        self.q.append((t, fn))
        self.q.sort()

    def poll(self):
        now = time.time()
        while len(self.q):
            t, fn = self.q[0]
            if t > now:
                break
            fn()
            self.q.pop(0)

#
#   Flash Check main function.

def flash_check(devname, jsonserver, mqttserver):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    checker = Checker(dev)
    reader = MqttReader()
    sched = Scheduler()

    def tick():
        print "tick"
        sched.add(10, tick)

    sched.add(10, tick)

    mqtt = broker.Broker("flash_check_" + time.ctime(), server=mqttserver)
    mqtt.subscribe("home/jeenet/" + devname, reader.on_device)
    mqtt.subscribe("home/jeenet/gateway", reader.on_gateway)

    mqtt.start()

    #checker.request()

    while True: # not checker.dead:
        try:
            msg = reader.pop()
            if msg:
                print msg
            sched.poll()
        except KeyboardInterrupt:
            break

    #checker.close()

    mqtt.stop()
    mqtt.join()

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-j", "--json", dest="json", default="jeenet")
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev")

    opts, args = p.parse_args()

    jsonserver = opts.json
    mqttserver = opts.mqtt
    devname = opts.dev

    flash_check(devname, jsonserver, mqttserver)

# FIN
