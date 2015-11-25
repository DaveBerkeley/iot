#!/usr/bin/python

import sys
import json
import time
import datetime
import optparse
import Queue
import base64
import copy
from StringIO import StringIO

# https://github.com/joshmarshall/jsonrpclib
import jsonrpclib

# https://github.com/cristianav/PyCRC
from PyCRC.CRC16 import CRC16

from jeenet.system.intelhex import convert
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
#

class TxQueue:

    def __init__(self):
        self.q = []
        self.free = 2

    def on_gateway(self, info):
        self.free, self.bsize = info
        #log(self.free, self.bsize)
        self.flush()

    def add(self, cmd):
        self.q.append(cmd)
        self.flush()

    def flush(self):
        while self.q and (self.free > 1):
            cmd = self.q.pop()
            cmd()
            self.free -= 1

txq = TxQueue()

#
#   Decouple MQTT messages from the reader thread

class MqttReader:

    def __init__(self, devname, server, txq):
        self.q = Queue.Queue()
        self.mqtt = broker.Broker("flash_io_" + time.ctime(), server=server)
        self.mqtt.subscribe("home/jeenet/" + devname, self.on_device)
        self.mqtt.subscribe("home/jeenet/gateway", self.on_gateway)
        self.txq = txq

    def start(self):
        self.mqtt.start()

    def stop(self):
        self.mqtt.stop()
        self.mqtt.join()

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

    def mqtt_handler(self, msg):
        ident, info = msg
        if ident == "D":
            rid = info.get("rid")
            if not rid is None:
                Command.on_reply(rid, info)
        elif ident == "G":
            self.txq.on_gateway(info)
        else:
            raise Exception(("Unknown ident", ident, info))

    def poll(self, handler=None):
        msg = self.pop()
        if not msg is None:
            fn = handler or self.mqtt_handler
            fn(msg)

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
#   Wrapper for device proxy commands to the gateway
#
#   Map commands to a req_id (rid)
#   and notify the command when its request arrives.

class Command:

    lut = {}

    def __init__(self, rid, fn, *args):
        self.rid = rid
        self.fn = fn
        self.args = args
        self.done = False
        self.die_timeout = None
        self.timeout = None
        self.retry = None
        self.exp = None
        def nowt(*args):
            log("callback not set", args)
        self.set_ack_nak(nowt, nowt)
        Command.add(rid, self)

    def __repr__(self):
        return "%s(rid=%d)" % (self.__class__.__name__, self.rid)

    def make_cb(self, fn):
        def xack(info):
            if self.done:
                return
            self.remove()
            fn(info)
        return xack

    def set_ack_nak(self, ack, nak):
        if ack:
            self.ack = self.make_cb(ack)
        if nak:
            self.nak = self.make_cb(nak)

    def start(self):
        # push to tx queue, defer running
        def fn():
            self.fn(self.rid, *self.args)
            if self.die_timeout:
                sched.add(self.die_timeout, self.on_timeout)
                self.die_timeout = None
                sched.add(self.timeout, self.on_retry)
        txq.add(fn)

    @staticmethod
    def add(rid, cmd):
        Command.lut[rid] = cmd

    def remove(self):
        if Command.lut.get(self.rid):
            del Command.lut[self.rid]
            self.done = True
            return True
        return False

    @staticmethod
    def on_reply(rid, info):
        cmd = Command.lut.get(rid)
        if cmd:
            cmd.reply(info)

    def on_timeout(self):
        if self.done:
            return
        log("timeout", self)
        self.nak("timeout")

    def on_retry(self):
        if self.done:
            return
        log("on_retry", self.retry, self)
        self.retry -= 1
        if self.retry == 0:
            self.nak("no more retries")
        else:
            if self.exp:
                self.timeout *= 2
            self()

    def set_timeout(self, die, retries=1, timeout=1, exp=False):
        self.die_timeout = die
        self.retry = retries
        self.timeout = timeout
        self.exp = exp

    def respond(self, info, cmd):
        if info.get("cmd") == cmd:
            self.ack(info)
        else:
            self.nak(info)

#
#

class InfoReq(Command):

    def __init__(self, flash, rid, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_info_req)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        self.respond(info, "info")

class SlotReq(Command):

    def __init__(self, flash, rid, slot, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_record_req, slot)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        self.respond(info, "record")

#
#

class Handler:

    def __init__(self, dev):
        self.dev = dev
        self.dead = False

    id = 0

    @staticmethod
    def make_id():
        Handler.id += 1
        if Handler.id > 255:
            Handler.id = 1
        return Handler.id

    #
    #

    def command(self, klass, *args, **kwargs):
        rid = Handler.make_id()
        nak = kwargs["nak"] or self.kill
        ack = kwargs["ack"]
        c = klass(self.dev, rid, *args, ack=ack, nak=nak)
        c.set_timeout(120, timeout=20, retries=5, exp=False)
        c.start()

    def info_req(self, ack=None, nak=None):
        self.command(InfoReq, ack=ack, nak=nak)

    def slot_req(self, slot, ack=None, nak=None):
        self.command(SlotReq, slot, ack=ack, nak=nak)

    #
    #

    def poll(self):
        info = self.f.read()
        if info:
            flash = info.get("flash")
            if flash:
                Command.on_reply(flash.get("rid"), flash)

    def kill(self, *args):
        log("KILL")
        self.dead = True

    def chain(self, ack):
        if ack:
            ack()
        else:
            log("Done")
            self.dead = True

    #
    #

    def test(self):

        slots = { "s" : [] }

        def on_slot(info):
            log("on_slot", info)
            slots["s"].append(info)
            if len(slots["s"]) == 8:
                self.chain(None)

        def on_info(info):
            log("on_info", info)

        self.info_req(ack=on_info)
        for i in range(8):
            self.slot_req(i, ack=on_slot)

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-j", "--json", dest="json", default="jeenet")
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev")
    p.add_option("-a", "--addr", dest="addr", type="int")
    p.add_option("-s", "--slot", dest="slot", type="int")
    p.add_option("-z", "--size", dest="size", type="int")
    p.add_option("-f", "--fname", dest="fname")
    p.add_option("-n", "--name", dest="name")
    p.add_option("-D", "--dir", dest="dir", action="store_true")
    p.add_option("-V", "--verify", dest="verify", action="store_true")
    p.add_option("-R", "--read", dest="read", action="store_true")
    p.add_option("-W", "--write", dest="write", action="store_true")

    opts, args = p.parse_args()

    devname = opts.dev
    jsonserver = opts.json
    mqttserver = opts.mqtt
    slot = opts.slot
    fname = opts.fname

    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    txq = TxQueue()
    sched = Scheduler()
    reader = MqttReader(devname, mqttserver, txq)

    reader.start()

    handler = Handler(dev)
    handler.test()

    while not handler.dead:
        try:
            reader.poll()
            sched.poll()
        except KeyboardInterrupt:
            break
        except Exception, ex:
            print ex
            break

    reader.stop()

# FIN
