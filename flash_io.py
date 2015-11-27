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
        log("gw", self.free, self.bsize)
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

    def __init__(self, rid, fn, *args, **kwargs):
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
            try:
                self.fn(self.rid, *self.args)
                if self.die_timeout:
                    sched.add(self.die_timeout, self.on_timeout)
                    self.die_timeout = None
                sched.add(self.timeout, self.on_retry)
            except Exception, ex:
                log("exception", str(ex))
                self.nak(ex)
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
            self.start()

    def set_timeout(self, policy):
        self.die_timeout = policy.die
        self.retry = policy.retries
        self.timeout = policy.timeout
        self.exp = policy.exp

    def respond(self, info, cmd):
        if info.get("cmd") == cmd:
            self.ack(info)
        else:
            self.nak(info)

#
#

class InfoReq(Command):

    def __init__(self, flash, rid, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_info_req, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "info")

class SlotReq(Command):

    def __init__(self, flash, rid, slot, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_record_req, slot, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "record")

class CrcReq(Command):

    def __init__(self, flash, rid, addr, size, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_crc_req, addr, size, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "crc")

class ReadReq(Command):

    def __init__(self, flash, rid, addr, size, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_read_req, addr, size, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "read")

class WriteReq(Command):

    def __init__(self, flash, rid, addr, b64, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_write, addr, b64, True, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "written")

class SlotWrite(Command):

    def __init__(self, flash, rid, slot, name, addr, size, crc, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_record, slot, name, addr, size, crc, *args, **kwargs)

    def reply(self, info):
        self.respond(info, "written")

class BootReq(Command):

    def __init__(self, flash, rid, *args, **kwargs):
        Command.__init__(self, rid, flash.flash_reboot, *args, **kwargs)

    def reply(self, info):
        pass

#
#

class RetryPolicy:

    def __init__(self, dev):
        self.die = 60 * 10
        self.timeout = dev.get_poll_period() * 1.5
        self.retries = 20
        self.exp = False

#
#

class Handler:

    def __init__(self, dev):
        self.dev = dev
        self.dead = False
        self.policy = RetryPolicy(dev)

    id = 0

    @staticmethod
    def make_id():
        Handler.id += 1
        if Handler.id > 255:
            Handler.id = 1
        return Handler.id

    #
    #   Command requests

    def command(self, klass, *args, **kwargs):
        rid = Handler.make_id()
        nak = kwargs.get("nak") or self.kill
        ack = kwargs["ack"]
        c = klass(self.dev, rid, *args, **kwargs)
        c.set_timeout(self.policy)
        assert nak
        assert ack
        c.set_ack_nak(ack, nak)
        c.start()

    def info_req(self, ack=None, nak=None):
        self.command(InfoReq, ack=ack, nak=nak)

    def slot_req(self, slot, ack=None, nak=None):
        self.command(SlotReq, slot, ack=ack, nak=nak)

    def crc_req(self, addr, size, ack=None, nak=None):
        self.command(CrcReq, addr, size, ack=ack, nak=nak)

    def read_req(self, addr, size, ack=None, nak=None):
        self.command(ReadReq, addr, size, ack=ack, nak=nak)

    def write_req(self, addr, b64, ack=None, nak=None):
        self.command(WriteReq, addr, b64, ack=ack, nak=nak)

    def slot_write(self, slot, name, addr, size, crc, ack=None, nak=None):
        self.command(SlotWrite, slot, name, addr, size, crc, ack=ack, nak=nak)

    def boot_req(self, ack=None, nak=None):
        self.command(BootReq, ack=ack, nak=nak)

    #
    #

    def poll(self):
        info = self.f.read()
        if info:
            flash = info.get("flash")
            if flash:
                Command.on_reply(flash.get("rid"), flash)

    def kill(self, *args):
        log("KILL", args)
        print "KILL", args
        self.dead = True

    def chain(self, ack):
        if ack:
            ack()
        else:
            log("Done")
            self.dead = True

    #
    #   Common rendering

    def on_no_info(self, info):
        print "No Flash Found"
        self.kill()

    def render_info(self, info):
        size = info.get("blocks") * info.get("size")
        bsize = info.get("packet")
        print "found flash size %d, buffsize %d" % (size, bsize)

    def render_slot(self, slot_info, info):
        slot = slot_info.get("slot")
        addr = slot_info.get("addr")
        size = slot_info.get("size")
        name = slot_info.get("name")
        crc = info.get("crc")
        scrc = slot_info.get("crc")
        if crc == scrc:
            end = "Ok"
        else:
            end = "Error, crc=%04X" % crc
        print "%02d %8s %7d %7d %04X %s" % (slot, name, addr, size, scrc, end)

    def progress(self, done, todo):
        percent = 100 * (done / float(todo))
        print int(100 - percent), "%", "\r",
        sys.stdout.flush()

    #
    #   Read the slot directory (possibly just one slot)

    def get_slots(self, slot_req=None, ack=None):

        slots = { 
            "s" : {},
            "slot" : None,
        }

        def show():
            while True:
                s = slots.get("slot")
                info = slots["s"].get(s)
                if not info:
                    break
                sinfo = info.get("info")
                self.render_slot(sinfo, info)
                slots["slot"] += 1

        def make_on_crc(slot_info):
            def on_crc(info):
                info["info"] = slot_info
                log("on_crc", slot_info)
                if slot_req is None:
                    slot = slot_info.get("slot")
                    slots["s"][slot] = info
                    show()
                    if len(slots["s"]) == 8:
                        self.chain(ack)
                else:
                    self.render_slot(slot_info, info)
                    self.chain(ack)
            return on_crc

        def on_slot(info):
            log("on_slot", info)
            addr = info.get("addr")
            size = info.get("size")
            slot = info.get("slot")
            name = info.get("name")
            crc = info.get("crc")
            self.crc_req(addr, size, ack=make_on_crc(info))

        def on_info(info):
            log("on_info", info)
            if not info.get("blocks"):
                return on_no_info()
            self.render_info(info)
            slots["slot"] = 0

        self.info_req(ack=on_info, nak=self.on_no_info)
        # make the slot requests anyway
        if not slot_req is None:
            self.slot_req(slot_req, ack=on_slot)
        else:
            for i in range(8):
                self.slot_req(i, ack=on_slot)

    #
    #   Read a binary file, possibly converting from IntelHex

    def read_file(self, filename):
        if filename.endswith(".hex"):
            print "Convert from IntelHex"
            io = StringIO()
            convert(filename, io, False)
            data = io.getvalue()
        else:
            data = open(filename).read()
        return data

    #
    #   Read a block and save the data as a file

    def read_block(self, start_addr, size, fname, ack=None):
        print "Read File", start_addr, size, fname

        if not size:
            self.kill("zero size file")

        if not fname:
            self.kill("no filename specified")

        s = {
            "f" : open(fname, "w"),
            "m" : {},
            "crc" : None,
            "blocks" : None,
        }
        queue = []

        def verify():
            s["f"].close()
            c = CRC16()
            raw = self.read_file(fname)
            crc = c.calculate(raw)

            if crc == s["crc"]:
                print "Verified okay, CRC=%04X" % crc
                self.chain(ack)
            else:
                print "Bad CRC %04X != %04X" % (crc, s["crc"])
                self.kill()

        def on_read(info):
            log("on_read", info)
            addr = info.get("addr")
            a = addr - start_addr
            data = info.get("data64")
            data = base64.b64decode(data)

            if s["m"].get(addr):
                f = s["f"]
                f.seek(a)
                f.write(data)
                del s["m"][addr]

                flush(1)
            else:
                log("duplicate?", addr)

            self.progress(len(s["m"]), s["blocks"])

            if not len(s["m"]):
                verify()

        def flush(n):
            for i in range(n):
                if queue:
                    fn = queue.pop()
                    if fn:
                        fn()

        def on_info(info):
            self.render_info(info)
            packet = info.get("packet")
            # mustn't send more than 256 requests!
            for a in range(start_addr, start_addr+size, packet):
                sz = min(packet, (start_addr+size) - a)
                def make(addr, size):
                    def fn():
                        self.read_req(addr, size, ack=on_read)
                    return fn
                queue.insert(0, make(a, sz))
                s["m"][a] = True

            s["blocks"] = len(queue)
            flush(10)

        def on_crc(info):
            log("on_crc", info)
            s["crc"] = info.get("crc")

        self.info_req(ack=on_info, nak=self.on_no_info)
        self.crc_req(start_addr, size, ack=on_crc)

    #
    #   Read a slot and save the data as a file

    def read(self, slot, fname, ack=None):

        print "Read slot", slot

        def on_slot(info):
            addr = info.get("addr")
            size = info.get("size")
            self.read_block(addr, size, fname, ack=ack)

        self.slot_req(slot, ack=on_slot)

    #
    #

    def make_name(self, name):
        if name is None:
            name = ""
        name += "-" * 8
        name = name.replace("?", "")
        return name[:8]

    #
    #   Write a file at start_addr, 
    #   optionaly saving the info as a slot/name.

    def write(self, start_addr, fname, slot, name=None, ack=None):

        if start_addr is None:
            self.kill("no address specified")
        if not fname:
            self.kill("no filename specified")

        queue = []
        packets = {}
        s = {}

        data = self.read_file(fname)

        c = CRC16()
        crc = c.calculate(data)

        print "Write", fname, "at address", start_addr, "size", len(data), "crc %04X" % crc

        def on_slot(info):
            log(info)
            print "Slot", slot, "written"
            self.chain(ack)

        def on_crc(info):
            log("on_crc", info)
            c = info.get("crc")
            if crc == c:
                print "Verified Okay, crc=%04X" % crc
                # write slot
                if slot is None:
                    self.chain(ack)
                else:
                    self.slot_write(slot, name, start_addr, len(data), crc, ack=on_slot)

            else:
                self.kill("Verify failed, bad CRC", crc, c)

        def flush(n):
            for i in range(n):
                if queue:
                    fn = queue.pop()
                    if fn:
                        fn()

        def on_write(info):
            log("on_write", info)
            self.progress(len(packets), s["packets"])
            addr = info.get("addr")
            crc = info.get("crc")
            if packets.get(addr):
                xcrc, fn = packets.get(addr)
                if crc != xcrc:
                    #self.kill("Bad CRC")
                    print "Bad CRC", info
                    queue.append(fn)
                del packets[addr]
            flush(1)

            if not packets:
                self.crc_req(start_addr, len(data), ack=on_crc)

        def make_fn(addr, data, ack):
            def fn():
                b64 = base64.b64encode(data)
                self.write_req(addr, b64, ack=ack)
            return fn

        def on_info(info):
            self.render_info(info)
            packet = info.get("packet")

            for addr in range(0, len(data), packet):
                size = min(packet, (len(data) - addr))
                d = data[addr:addr+size]
                a = start_addr + addr
                fn = make_fn(a, d, on_write)
                queue.append(fn)
                c = CRC16()
                crc = c.calculate(d)
                packets[a] = crc, fn

            if len(data) == 0: # empty file
                fn = make_fn(0, "", on_write)
                queue.append(fn)
                crc = 0
                packets[0] = crc, fn

            s["packets"] = len(queue)
            flush(10)

        self.info_req(ack=on_info, nak=self.on_no_info)

    #
    #   Verify a block against a file

    def verify_block(self, fname, addr, size, ack=None):
        data = self.read_file(fname)
        c = CRC16()
        crc = c.calculate(data)

        if size is None:
            size = len(data)

        print "%s addr=%d size=%d" % (fname, addr, size)

        def on_crc(info):
            if crc == info.get("crc"):
                print "Verifies okay, crc=%04X" % crc
                self.chain(ack)
            else:
                self.kill("Bad CRC")

        self.crc_req(addr, size, ack=on_crc)

    #
    #   Verify a slot against a file

    def verify(self, fname, slot, ack=None):

        if not fname:
            self.kill("filename not specified")
        if slot is None:
            self.kill("slot not specified")

        def on_slot(info):
            self.verify_block(fname, info.get("addr"), info.get("size"), ack)

        self.slot_req(slot, ack=on_slot)

    #
    #   Copy one slot to another, possibly giving it a new name.

    def copy(self, from_slot, to_slot, name, ack=None):

        print "Copy slot", from_slot, "to slot", to_slot,
        if name:
            print "as", name
        else:
            print

        if from_slot is None:
            self.kill("Source slot not specified")
        if to_slot is None:
            self.kill("Destination slot not specified")

        def on_write(info):
            self.chain(ack)

        def on_slot(info):
            n = name or info.get("name")
            n = self.make_name(n)
            addr = info.get("addr")
            size = info.get("size")
            crc = info.get("crc")
            self.slot_write(to_slot, n, addr, size, crc, ack=on_write)

        self.slot_req(from_slot, ack=on_slot)

    #
    #   Force the remote device to reboot

    def boot(self, ack=None):

        def on_boot(info):
            pass

        self.boot_req(ack=on_boot)
        self.chain(ack)

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
    p.add_option("-v", "--verbose", dest="verbose", action="store_true")
    p.add_option("-D", "--dir", dest="dir", action="store_true")
    p.add_option("-V", "--verify", dest="verify", action="store_true")
    p.add_option("-R", "--read", dest="read", action="store_true")
    p.add_option("-W", "--write", dest="write", action="store_true")
    p.add_option("-A", "--audit", dest="audit", action="store_true")
    p.add_option("-C", "--copy", dest="copy", type="int")
    p.add_option("-B", "--boot", dest="boot", action="store_true")

    opts, args = p.parse_args()

    devname = opts.dev
    jsonserver = opts.json
    mqttserver = opts.mqtt
    slot = opts.slot
    fname = opts.fname
    verbose = opts.verbose

    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    if opts.audit:
        dev = DeviceProxy(server, "gateway")
        names = dev.get_devices()
        names.sort()
        now = time.time()
        for name in names:
            d = DeviceProxy(server, name)
            try:
                t = now - d.get_last_message()
            except TypeError:
                t = -1
            sleepy = d.sleepy()
            dt = d.get_poll_period()
            print "%-20s sleepy=%-5s period=%-3d last=%.1f" % (name, sleepy, dt, t)
        sys.exit()

    dev = DeviceProxy(server, devname)

    txq = TxQueue()
    sched = Scheduler()
    reader = MqttReader(devname, mqttserver, txq)

    reader.start()

    handler = Handler(dev)

    if opts.dir:
        handler.get_slots(opts.slot)
    elif opts.read:
        if not opts.slot is None:
            handler.read(opts.slot, opts.fname)
        else:
            handler.read_block(opts.addr, opts.size, opts.fname) 
    elif opts.write:
        handler.write(opts.addr, opts.fname, opts.slot, opts.name)
    elif opts.verify:
        if not opts.slot is None:
            handler.verify(opts.fname, opts.slot)
        else:
            handler.verify_block(opts.fname, opts.addr, opts.size)
    elif not opts.copy is None:
        handler.copy(opts.slot, opts.copy, opts.name) 
    elif opts.boot:
        handler.boot()
    else:
        print "No command specified"
        handler.dead = True

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
