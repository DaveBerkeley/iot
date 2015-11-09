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

next_rid = int(time.time())

def make_rid():
    global next_rid
    next_rid += 1
    return next_rid & 0xFF

#
#

class Command:

    lut = {} # {rid : command} map

    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.rid = make_rid()
        self.args = args
        self.kwargs = kwargs
        self.lut[self.rid] = self

    def __call__(self):
        return self.fn(self.rid, *self.args, **self.kwargs)

    def response(self, info):
        raise Exception("implement in subclass")

    def remove(self):
        if self.lut.get(self.rid) == self:
            del self.lut[self.rid]

    @staticmethod
    def on_response(rid, info):
        c = Command.lut.get(rid)
        if c:
            c.response(info)
        else:
            print "command not found", rid, info

#
#

class InfoReq(Command):

    def __init__(self, dev, sched, ack, nak):
        Command.__init__(self, dev.flash_info_req)
        self.ack = ack
        self.nak = nak
        self.done = False
        sched.add(10, self.timeout)

    def __call__(self):
        try:
            Command.__call__(self)
        except Exception, ex:
            self.done = True
            self.nak(ex)

    def response(self, info):
        self.remove()
        self.done = True
        # TODO : info may mean nak
        self.ack(info)

    def timeout(self):
        if not self.done:
            self.nak("timeout")

#
#

class Checker:
    def __init__(self, dev, sched):
        self.dev = dev
        self.sched = sched
    def start(self):
        c = InfoReq(self.dev, self.sched, self.info_good, self.info_fail)
        c()
    def info_fail(self, info):
        print "info fail", info
    def info_good(self, info):
        print "info", info

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
    def poll(self, handler):
        msg = self.pop()
        if not msg is None:
            handler(msg)

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
            self.q.pop(0)
            fn()

#
#   Flash Check main function.

def flash_check(devname, jsonserver, mqttserver):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    sched = Scheduler()
    checker = Checker(dev, sched)
    reader = MqttReader()

    mqtt = broker.Broker("flash_check_" + time.ctime(), server=mqttserver)
    mqtt.subscribe("home/jeenet/" + devname, reader.on_device)
    mqtt.subscribe("home/jeenet/gateway", reader.on_gateway)

    mqtt.start()

    def mqtt_handler(msg):
        print msg
        ident, info = msg
        if ident == "D":
            rid = info.get("rid")
            if not rid is None:
                Command.on_response(rid, info)

    checker.start()

    while True: # not checker.dead:
        try:
            reader.poll(mqtt_handler)
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
