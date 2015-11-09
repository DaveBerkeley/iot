#!/usr/bin/python

import sys
import json
import time
import datetime
import optparse
import Queue
import base64

# https://github.com/joshmarshall/jsonrpclib
import jsonrpclib

# https://github.com/cristianav/PyCRC
from PyCRC.CRC16 import CRC16

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
#   Decouple MQTT messages from the reader thread

class MqttReader:

    def __init__(self, devname, server):
        self.q = Queue.Queue()
        self.mqtt = broker.Broker("flash_io_" + time.ctime(), server=server)
        self.mqtt.subscribe("home/jeenet/" + devname, self.on_device)
        self.mqtt.subscribe("home/jeenet/gateway", self.on_gateway)

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
                Command.on_response(rid, info)
        elif ident == "G":
            txq.on_gateway(info)
        else:
            raise Exception(("Unknown ident", ident, info))

    def poll(self, handler=None):
        if handler is None:
            handler = self.mqtt_handler
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
#   Send command to the jsonrpc when there is room on the gateway.

class SendQueue:

    def __init__(self):
        self.free = 2
        self.bsize = 0
        self.q = []

    def tx(self, cmd):
        self.q.append(cmd)
        self.flush()

    def on_gateway(self, info):
        # callback from MQTT notification
        free, bsize = info
        self.free = free
        self.bsize = bsize
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

    next_rid = int(time.time()*1000)

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
        # callback for MQTT notify
        c = Command.lut.get(rid)
        if c:
            c.response(info)
        else:
            #log("command not found", rid, info)
            pass

#
#   Implement retry / timeout for commands

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
        else:
            self.nak(info)

#
#

class FlashCrcReq(Command, Retry):

    def __init__(self, dev, sched, addr, size, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_crc_req, addr, size)
        Retry.__init__(self, sched, trys=5, timeout=10)
        self.set_ack_nak(ack, nak)

    def __call__(self):
        Retry.__call__(self)

    def response(self, info):
        if info.get("cmd") == "crc":
            self.ack(info)
        else:
            self.nak(info)

#
#

class FlashWriteReq(Command, Retry):

    def __init__(self, dev, sched, addr, b64, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_write, addr, b64, True)
        Retry.__init__(self, sched, trys=5, timeout=1)
        self.set_ack_nak(ack, nak)

    def get_timeout(self):
        # exponential backoff
        n = self.timeout
        self.timeout *= 2
        return n

    def __call__(self):
        Retry.__call__(self)

    def response(self, info):
        if info.get("cmd") == "written":
            self.ack(info)
        else:
            self.nak(info)

#
#

class FlashSlotWrite(Command, Retry):

    def __init__(self, dev, sched, slot, name, addr, size, crc, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_record, slot, name, addr, size, crc)
        Retry.__init__(self, sched, trys=5, timeout=1)
        self.set_ack_nak(ack, nak)

    def get_timeout(self):
        # exponential backoff
        n = self.timeout
        self.timeout *= 2
        return n

    def __call__(self):
        Retry.__call__(self)

    def response(self, info):
        if info.get("cmd") == "written":
            self.ack(info)
        else:
            self.nak(info)

#
#   Run a set of commands in parallel

class Batch:

    def __init__(self):
        self.doing = {}

    def run(self, fn, ack, *args, **kwargs):
        def xack(info):
            del self.doing[xack]
            ack(info)

        self.doing[xack] = True
        fn(xack, *args, **kwargs)

    def done(self):
        return len(self.doing) == 0

    def size(self):
        return len(self.doing)

#
#   Run a set of commands in sequence

class Chain:

    def __init__(self):
        self.doing = []

    def run(self, fn, ack, *args, **kwargs):
        def xack(info):
            # remove the command from the start of the list
            self.doing = self.doing[1:]
            ack(info)
            if not self.done():
                # run the next command in the list
                fn, cb, a, k = self.doing[0]
                fn(cb, *a, **k)

        # add the command to the end of the list
        self.doing.append((fn, xack, args, kwargs))
        # run it now if it is the first command
        if len(self.doing) == 1:
            fn(xack, *args, **kwargs)

    def done(self):
        return len(self.doing) == 0

    def size(self):
        return len(self.doing)

#
#

def make_slot_name(slot, name):
    if slot == 0:
        name = name or "BOOTDATA"
    else:
        name = name or "FILEDATA"
    name += "-" * 8
    return name[:8]

#
#

class Checker:

    def __init__(self, dev, sched):
        self.dev = dev
        self.sched = sched
        self.dead = False

    def fail(self, info):
        print "fail", info
        self.dead = True

    #   Flash Commands

    def info_req(self, ack, nak=None):
        if nak is None:
            nak = self.fail
        FlashInfoReq(self.dev, self.sched, ack, nak)()

    def rec_req(self, ack, rec):
        FlashRecordReq(self.dev, self.sched, rec, ack, self.fail)()

    def crc_req(self, ack, addr, size):
        FlashCrcReq(self.dev, self.sched, addr, size, ack, self.fail)()

    def write_req(self, ack, addr, b64):
        FlashWriteReq(self.dev, self.sched, addr, b64, ack, self.fail)()

    def write_slot(self, ack, slot, slotname, addr, size, crc):
        name = make_slot_name(slot, slotname)
        FlashSlotWrite(self.dev, self.sched, slot, name, addr, size, crc, ack, self.fail)()

    #

    def slot_request(self, slot=None):

        def on_slot(info):
            # handler for slot response
            slot = info["slot"]
            addr = info["addr"]
            size = info["size"]
            crc = info["crc"]

            txt = "%02d %s %8d %6d %04X" % (slot, info["name"], addr, size, crc)

            def on_crc(info):
                # handler for crc response
                okay = "Error, crc=%04X" % info.get("crc")
                if info.get("crc") == crc:
                    if info.get("addr") == addr:
                        if info.get("size") == size:
                            okay = "Ok"
                print txt, okay
                if requests.done():
                    self.dead = True

            # chain the CRC request
            requests.run(self.crc_req, on_crc, addr, size)

        def on_info(info):
            # handler for flash info response
            size, buff = info
            print "found flash size", size, "buffsize", buff
            if slot is None:
                for i in range(8):
                    requests.run(self.rec_req, on_slot, i)
            else:
                requests.run(self.rec_req, on_slot, slot)

        # chain the requests
        requests = Chain()
        self.info_req(on_info)

    #
    #

    def write_file(self, start_addr, fname, slot=None, name="--------"):
        print "write file", start_addr, fname, slot

        raw = open(fname).read()
        c = CRC16()
        crc = c.calculate(raw)

        def write_slot():
            if slot is None:
                self.dead = True
                return

            def ack(info):
                print "Slot %d '%s' written" % (slot, str(name))
                self.dead = True

            self.write_slot(ack, slot, name, start_addr, len(raw), crc)

        def verify():
            print "Verify ..."

            def on_crc(info):
                okay = False
                if info.get("crc") == crc:
                    if info.get("addr") == start_addr:
                        if info.get("size") == len(raw):
                            okay = True

                if not okay:
                    print "Verify failed", "%04X" % crc, "got", "%04X" % info.get("crc")
                    self.dead = True
                else:
                    print "Verified okay"
                    write_slot()

            self.crc_req(on_crc, start_addr, len(raw))

        def make_ack(addr, size, crc, b64):
            # save the loop state as a closure
            def on_write(info):
                okay = False
                if info.get("addr") == addr:
                    if info.get("size") == size:
                        if info.get("crc") == crc:
                            print "\r            \r",
                            print requests.size(),
                            sys.stdout.flush()
                            okay = True

                if not okay:
                    print "Failed", addr, size, "%04X" % crc
                    # run again if failed the write
                    requests.run(self.write_req, on_write, addr, b64)
                if requests.done():
                    verify()
            return on_write

        def on_info(info):
            # handler for flash info response
            size, buff = info
            print "found flash size", size, "buffsize", buff
            assert txq.bsize, "need to know gateway SaF buffer size"

            size = min(buff, txq.bsize)
            for addr in range(0, len(raw), size):
                d = raw[addr:addr+size]
                b64 = base64.b64encode(d)
                c = CRC16()
                crc = c.calculate(d)

                write_addr = addr + start_addr
                ack = make_ack(write_addr, len(d), crc, b64)
                requests.run(self.write_req, ack, write_addr, b64)

            if len(raw) == 0:
                verify()

        # batch the requests
        requests = Chain()
        self.info_req(on_info)

    def verify_file(self, fname, slot):
        raw = open(fname).read()
        c = CRC16()
        crc = c.calculate(raw)
        size = len(raw)
        del raw

        print "verify '%s' size=%d crc=%04X against slot=%d" % (fname, size, crc, slot)

        def on_slot(info):
            okay = False
            if info.get("size") == size:
                if info.get("crc") == crc:
                    okay = True

            if okay:
                print "Validates okay"
            else:
                print "Files differ size=%d crc=%04X" % (info.get("size"), info.get("crc")) 

            self.dead = True

        def on_info(info):
            size, _ = info
            if not size:
                print "No Flash Fitted"
                self.dead = True

            #print "Found", size, "flash"
            self.rec_req(on_slot, slot)

        self.info_req(on_info)

#
#   Flash IO main function.

def flash_io(devname, jsonserver, mqttserver, dir_req, addr, slot, fname, name, verify):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    sched = Scheduler()
    checker = Checker(dev, sched)
    reader = MqttReader(devname, mqttserver)

    if dir_req:
        checker.slot_request(slot)
    if verify:
        checker.verify_file(fname, slot)
    elif addr != None:
        checker.write_file(addr, fname, slot, name)

    reader.start()

    while not checker.dead:
        try:
            reader.poll()
            sched.poll()
        except KeyboardInterrupt:
            break
        except Exception, ex:
            print ex
            break

    reader.stop()

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-j", "--json", dest="json", default="jeenet")
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev")
    p.add_option("-D", "--dir", dest="dir", action="store_true")
    p.add_option("-a", "--addr", dest="addr", type="int")
    p.add_option("-s", "--slot", dest="slot", type="int")
    p.add_option("-f", "--fname", dest="fname")
    p.add_option("-n", "--name", dest="name")
    p.add_option("-V", "--verify", dest="verify", action="store_true")

    opts, args = p.parse_args()

    jsonserver = opts.json
    mqttserver = opts.mqtt
    devname = opts.dev

    flash_io(devname, jsonserver, mqttserver, opts.dir, opts.addr, opts.slot, opts.fname, opts.name, opts.verify)

# FIN
