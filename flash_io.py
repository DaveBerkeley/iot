#!/usr/bin/python

import sys
import json
import time
import datetime
import optparse
import Queue
import base64
import copy

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
#   Wrapper for device proxy commands to the gateway
#
#   Map commands to a req_id (rid)
#   and notify the command when its request arrives.

class Command:

    # make unique request id (rid)
    next_rid = int(time.time()*1000)

    # {rid : command} map
    lut = {} 

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
        # called when message with the same rid is rxd.
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
        if self.done:
            return
        if self.trys > 0:
            # re-run the command
            self()
        else:
            self.nak("timeout")

#
#   Implement Commmands for each flash_xxx API call.

#
#   dev.flash_info_req()

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
#   dev.flash_record_req(slot)

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
#   dev.flash_crc_req

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
#   dev.flash_write(addr, data, is_b64)

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
#   dev.flash_record(slot, name, addr,size, crc)

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
#   dev.flash_read_req(addr, size)

class FlashReadReq(Command, Retry):

    def __init__(self, dev, sched, addr, size, ack=None, nak=None):
        Command.__init__(self, txq, dev.flash_read_req, addr, size)
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
        if info.get("cmd") == "read":
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

    def read_req(self, ack, addr, size):
        FlashReadReq(self.dev, self.sched, addr, size, ack, self.fail)()

    #
    #

    #
    #   Slot directory

    def slot_request(self, r, slot=None):

        r.begin(slot)

        def on_slot(info):
            # handler for slot response
            slot = info["slot"]
            addr = info["addr"]
            size = info["size"]
            crc = info["crc"]

            txt = "%02d %s %8d %6d %04X" % (slot, info["name"], addr, size, crc)

            r.on_slot(info)

            def on_crc(info):
                # handler for crc response
                okay = False
                if info.get("crc") == crc:
                    if info.get("addr") == addr:
                        if info.get("size") == size:
                            okay = True

                r.on_crc(slot, info, okay)

                if requests.done():
                    self.dead = True

            # chain the CRC request
            requests.run(self.crc_req, on_crc, addr, size)

        def on_info(info):
            # handler for flash info response
            size, buff = info

            r.on_info(info)

            if slot is None:
                for i in range(8):
                    requests.run(self.rec_req, on_slot, i)
            else:
                requests.run(self.rec_req, on_slot, slot)

        # chain the requests
        requests = Chain()
        self.info_req(on_info)

    #
    #   Write File

    def write_file(self, r, start_addr, fname, slot=None, name="--------"):

        r.begin(start_addr, fname, slot)

        raw = open(fname).read()
        c = CRC16()
        crc = c.calculate(raw)

        def write_slot():
            if slot is None:
                self.dead = True
                return

            def ack(info):
                r.on_slot(info, slot, name)
                self.dead = True

            self.write_slot(ack, slot, name, start_addr, len(raw), crc)

        def verify():

            def on_crc(info):
                okay = False
                if info.get("crc") == crc:
                    if info.get("addr") == start_addr:
                        if info.get("size") == len(raw):
                            okay = True

                r.on_verify(info, okay)

                if not okay:
                    self.dead = True
                else:
                    write_slot()

            self.crc_req(on_crc, start_addr, len(raw))

        def make_ack(addr, size, crc, b64):
            # save the loop state as a closure
            def on_write(info):
                okay = False
                if info.get("addr") == addr:
                    if info.get("size") == size:
                        if info.get("crc") == crc:
                            okay = True

                if not okay:
                    # run again if failed the write
                    requests.run(self.write_req, on_write, addr, b64)

                r.on_write(info, okay, requests.size())

                if requests.done():
                    verify()
            return on_write

        def on_info(info):
            # handler for flash info response
            size, buff = info
            assert txq.bsize, "Need to know gateway SaF buffer size"

            r.on_info(info)

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

    #
    #   Verify File

    def verify_file(self, r, fname, slot):
        raw = open(fname).read()
        c = CRC16()
        crc = c.calculate(raw)
        size = len(raw)
        del raw

        r.begin(fname, size, crc, slot)

        def on_slot(info):
            okay = False
            if info.get("size") == size:
                if info.get("crc") == crc:
                    okay = True

            r.on_slot(info, okay)

            self.dead = True

        def on_info(info):
            size, _ = info

            r.on_info(info)

            if not size:
                self.dead = True

            self.rec_req(on_slot, slot)

        self.info_req(on_info)

    #
    #   Read File

    def read_file(self, r, fname, slot, addr=None, fsize=None):

        r.begin(fname, slot)

        block = {}

        f = open(fname, "w")
        block["f"] = f

        def on_read(info):
            addr = info.get("addr") - block["start"]
            size = info.get("size")
            data = info.get("data64")
            data = base64.b64decode(data)

            if len(data) != size:
                r.on_error(info)
                self.dead = True
                return

            r.on_read(info)

            f = block["f"]
            f.seek(addr)
            f.write(data)

            if requests.done():
                f.close()
                self.dead = True

        def on_slot(info):
            start_addr = info.get("addr")
            size = info.get("size")
            block["start"] = start_addr

            r.on_slot(info)

            for addr in range(0, size, block["size"]):
                end = min(addr + block["size"], size)
                s = end - addr
                requests.run(self.read_req, on_read, start_addr + addr, s)

        def on_info(info):
            size, pbuff = info

            r.on_info(info)

            if not size:
                self.dead = True

            assert txq.bsize, "need to know gateway SaF buffer size"
            block["size"] = min(pbuff, txq.bsize)

            if slot is None:
                # fake the slot info
                d = { "addr" : addr, "size" : fsize }
                on_slot(d)
            else:
                # request the slot info
                self.rec_req(on_slot, slot)

        # chain the requests
        requests = Chain()
        self.info_req(on_info)

#
#   Renderers

class Renderer:
    def on_info(self, info):
        size, buff = info
        if size:
            print "found flash size", size, "buffsize", buff
        else:
            print "No flash found"

class SlotRenderer(Renderer):

    def __init__(self):
        self.txt = {}

    def begin(self, slot):
        print "Slot directory", slot or ""

    def on_slot(self, info):
        slot = info["slot"]
        addr = info["addr"]
        size = info["size"]
        crc = info["crc"]

        txt = "%02d %s %8d %6d %04X" % (slot, info["name"], addr, size, crc)
        self.txt[slot] = txt

    def on_crc(self, slot, info, okay):
        txt = self.txt[slot]
        if okay:
            print txt, "Ok"
        else:
            print txt, "Error, crc=%04X" % info.get("crc")

class WriteRenderer(Renderer):

    def begin(self, addr, fname, slot):
        print "Write", fname, "to addr", addr, "slot", slot

    def on_write(self, info, okay, q):
        if okay:
            print "\r            \r",
            print q,
            sys.stdout.flush()
        else:
            addr = info.get("addr")
            size = info.get("size")
            crc = info.get("crc")
            print "Failed", addr, size, "%04X" % crc

    def on_verify(self, info, okay):
        if okay:
            print "Verified okay"
        else:
            print "Verify failed, crc was %04X" % info.get("crc")

    def on_slot(self, info, slot, name):
        print "Slot %d '%s' written" % (slot, str(name))

class VerifyRenderer(Renderer):

    def begin(self, fname, size, crc, slot):
        print "verify '%s' size=%d crc=%04X against slot=%d" % (fname, size, crc, slot)

    def on_slot(self, info, okay):
        if okay:
            print "Validates okay"
        else:
            print "Files differ size=%d crc=%04X" % (info.get("size"), info.get("crc")) 

class ReadRenderer(Renderer):

    def begin(self, fname, slot):
        print "Read File", fname, "from slot", slot

    def on_slot(self, info):
        print "Reading %d bytes at address %d" % (info.get("size"), info.get("addr"))

    def on_read(self, info):
        print "\r              \r",
        print info.get("addr"),
        sys.stdout.flush()

    def on_error(self, info):
        print "Read Error"

#
#   Flash IO main function.

def flash_io(opts, renderer):

    devname = opts.dev
    jsonserver = opts.json
    mqttserver = opts.mqtt
    slot = opts.slot
    fname = opts.fname

    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    sched = Scheduler()
    checker = Checker(dev, sched)
    reader = MqttReader(devname, mqttserver)

    if opts.dir:
        checker.slot_request(renderer, slot)
    elif opts.verify:
        assert fname, "must have filename"
        assert not slot is None, "must specify slot"
        checker.verify_file(renderer, fname, slot)
    elif opts.read:
        assert fname, "must have filename"
        checker.read_file(renderer, fname, slot, opts.addr, opts.size)
    elif opts.write:
        assert fname, "must have filename"
        checker.write_file(renderer, opts.addr, fname, slot, opts.name)

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
#   API

class FlashDevice:

    def __init__(self, jsonserver, mqttserver, devname):
        self.json = jsonserver
        self.mqtt = mqttserver
        self.dev = devname
        self.fname = None
        self.dir = None
        self.verify = None
        self.read = None

def slot_request(renderer, flash_device, slot=None):
    fd = copy.copy(flash_device)
    fd.slot = slot
    fd.dir = True
    flash_io(fd, renderer)

def verify_request(renderer, flash_device, slot, fname):
    fd = copy.copy(flash_device)
    fd.slot = slot
    fd.fname = fname
    fd.verify = True
    flash_io(fd, renderer)

def read_request(renderer, flash_device, slot, fname, addr=None, size=None):
    fd = copy.copy(flash_device)
    fd.slot = slot
    fd.fname = fname
    fd.read = True
    fd.addr = addr
    fd.size = size
    flash_io(fd, renderer)

def write_request(renderer, flash_device, slot, fname, addr, slotname=None):
    fd = copy.copy(flash_device)
    fd.slot = slot
    fd.fname = fname
    fd.write = True
    fd.addr = addr
    fd.name = slotname
    flash_io(fd, renderer)

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

    if opts.dir:
        r = SlotRenderer()
    elif opts.verify:
        r = VerifyRenderer()
    elif opts.read:
        r = ReadRenderer()
    else:
        r = WriteRenderer()

    flash_io(opts, r)

# FIN
