#!/usr/bin/python

import sys
import os
import json
import time
import datetime
import optparse
import Queue

import jsonrpclib

from jeenet.system.core import DeviceProxy
import broker

#
#

verbose = True

def log(*args):
    if not verbose:
        return
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print

#
#   Send command to the jsonrpc when there is room on the gateway.

class SendQueue:

    def __init__(self):
        self.free = 2
        self.q = []

    def tx(self, cmd):
        self.q.append(cmd)
        self.flush()

    def on_gateway(self, info):
        free, bsize = info
        #print free, bsize
        self.free = free
        self.flush()

    def flush(self):
        while self.free > 1:
            if not self.q:
                break
            cmd, self.q = self.q[0], self.q[1:]
            cmd()
            self.free -= 1

txq = SendQueue()

#
#

class Command:

    next_rid = os.getpid()

    lut = {} # {rid : command} map

    def __init__(self, txq, fn, *args, **kwargs):
        self.txq = txq
        self.fn = fn
        self.rid = self.make_rid()
        self.args = args
        self.kwargs = kwargs
        self.lut[self.rid] = self
        self.done = False
        self.ack = self.kill
        self.nak = self.kill

    @staticmethod
    def make_rid():
        Command.next_rid += 1
        return Command.next_rid & 0xFF

    def kill(self, *args):
        if not self.done:
            self.done = True
            self.remove()
            return True
        return False

    def set_ack_nak(self, ack, nak):
        def handler(fn):
            def inner(info):
                if self.kill():
                    fn(info)
            return inner
        if ack:
            self.ack = handler(ack)
        if nak:
            self.nak = handler(nak)

    def __call__(self):
        try:
            def fn():
                self.fn(self.rid, *self.args, **self.kwargs)
            self.txq.tx(fn)
        except Exception, ex:
            self.nak(ex)

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
            #log("command not found", rid, info)
            pass

#
#

class Retry:

    def __init__(self, sched, timeout=10, trys=1):
        self.sched = sched
        self.timeout = timeout
        self.trys = trys

    def __call__(self):
        Command.__call__(self)
        if self.trys <= 0:
            return
        self.sched.add(self.get_timeout(), self.timeout_fn)
        self.trys -= 1

    def get_timeout(self):
        # overide for eg. exponential backoff
        return self.timeout

    def timeout_fn(self):
        #log("timeout", self.trys, self.fn)
        if self.done:
            return
        if self.trys > 0:
            self()
        else:
            self.nak("timeout")

#
#

class FlashInfoReq(Command, Retry):

    def __init__(self, dev, sched, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_info_req)
        Retry.__init__(self, sched, trys=5, timeout=1)
        self.set_ack_nak(ack, nak)

    def __call__(self):
        Retry.__call__(self)

    def get_timeout(self):
        # exponential backoff
        n = self.timeout
        self.timeout *= 2
        return n

    def response(self, info):
        if info.get("cmd") != "info":
            self.nak(info)
            return
        size = info.get("blocks", 0) * info.get("size", 0)
        packet = info.get("packet", 0)
        if size:
            self.ack((size, packet))
        else:
            self.nak("no flash fitted")

#
#

class FlashRecordReq(Command, Retry):

    def __init__(self, dev, sched, rec, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_record_req, rec)
        Retry.__init__(self, sched, trys=5, timeout=10)
        self.set_ack_nak(ack, nak)

    def __call__(self):
        Retry.__call__(self)

    def response(self, info):
        if info.get("cmd") == "record":
            self.ack(info)

#
#

class Checker:

    def __init__(self, dev, sched):
        self.dev = dev
        self.sched = sched
        self.dead = False

    def info_req(self):
        FlashInfoReq(self.dev, self.sched, self.info_good, self.fail)()

    def rec_req(self, rec):
        FlashRecordReq(self.dev, self.sched, rec, self.rec_good, self.fail)()

    def start(self):
        self.info_req()

    def fail(self, info):
        print "info fail", info
        self.dead = True

    def info_good(self, info):
        #log("size", info)
        size, buff = info
        print "found flash size", size, "buffsize", buff
        # start requesting the slots
        self.recs = {}
        for i in range(8):
            self.rec_req(i)
            self.recs[i] = True

    def rec_good(self, info):

        slot = info["slot"]

        print slot,
        print info["name"],
        print "%08d" % info["addr"],
        print "%06d" % info["size"],
        print "%04X" % info["crc"],
        print

        if self.recs.get(slot):
            del self.recs[slot]
        if not len(self.recs):
            self.dead = True

#
#   Decouple MQTT messages from the reader thread

class MqttReader:

    def __init__(self):
        self.q = Queue.Queue()

    def add(self, ident, info):
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
#   Not really a scheduler so much as an event generator.
#
#   Hard to get it simpler than this.

class Scheduler:

    def __init__(self):
        self.q = []

    def add(self, dt, fn):
        t = time.time() + dt
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
        ident, info = msg
        if ident == "D":
            rid = info.get("rid")
            if not rid is None:
                Command.on_response(rid, info)
        elif ident == "G":
            txq.on_gateway(info)
        else:
            raise Exception(("Unknown ident", ident, info))

    checker.start()

    while not checker.dead:
        try:
            reader.poll(mqtt_handler)
            sched.poll()
        except KeyboardInterrupt:
            break
        except Exception, ex:
            print ex
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
