#!/usr/bin/python

import struct
import time
import sys
import optparse
from StringIO import StringIO

import serial

# https://github.com/cristianav/PyCRC
from PyCRC.CRC16 import CRC16

from jeenet.system.flash import FlashInterface, log
import jeenet.system.bencode as bencode
from jeenet.system.intelhex import convert

import flash_io
from flash_io import Scheduler, Chain

from jeenet.system import core

core.verbose = False

#
#

class Flash(FlashInterface):

    api = []
    flash_flag = 0x0800
    ack_flag = 0x8000
    fmt_header = "<BBH"

    id = 0

    @staticmethod
    def make_id():
        Flash.id += 1
        if Flash.id > 255:
            Flash.id = 1
        return Flash.id

    def __init__(self, serdev="/dev/ttyUSB0"):
        self.s = serial.Serial(serdev, 57600, timeout=0.1, xonxoff=0, rtscts=0)
        self.dev_id = 0xaa
        # serial port seems to lose the first char?
        self.s.write("\0")

    def make_raw(self, flags, fields, msg_id=None):
        # fields as [ (bit_mask, fmt, value), ... ] in binary order

        mid = msg_id or Flash.make_id()
        mask = flags
        args = ""
        for bit, fmt, value in fields:
            if bit:
                args += struct.pack(fmt, value)
            mask |= bit

        raw = struct.pack(self.fmt_header, mid, self.dev_id, mask)
        return mid, raw + args

    def tx_message(self, mid, raw, name, flags):
        #print mid, `raw`, name, flags
        self.s.write(bencode.encode([ self.dev_id, raw ]))
        self.s.flush()

    def read(self):
 
        msg = ""
        while True:
            c = self.s.read(1)
            if not c:
                break
            msg += c

        if not msg:
            return None

        node, raw = self.parse(msg)
        return self.flash_to_info(raw)

    def parse(self, msg):

        # Bencode parse the response
        class G:
            def __init__(self, msg):
                self.msg = msg
                self.i = 0
            def get(self):
                i = self.i
                self.i += 1
                return self.msg[i]

        g = G(msg)
        parser = bencode.Parser(g.get)
        node, raw = parser.get()
        return node, raw

#
#

class Command:

    lut = {}

    def __init__(self, rid, fn, *args):
        self.rid = rid
        self.fn = fn
        self.args = args
        self.done = False
        def nowt(*args):
            print "callback not set", args
        self.set_ack_nak(nowt, nowt)
        Command.add(rid, self)

    #def __repr__(self):
    #    return "%s %s" % (self.fn, self.args)

    def make_cb(self, fn):
        def xack(info):
            if self.done:
                return
            self.remove()
            fn(info)
        return xack

    def set_ack_nak(self, ack, nak):
        #print nak
        if ack:
            self.ack = self.make_cb(ack)
        if nak:
            self.nak = self.make_cb(nak)

    def __call__(self):
        self.fn(self.rid, *self.args)

    @staticmethod
    def add(rid, cmd):
        Command.lut[rid] = cmd

    def remove(self):
        if Command.lut.get(self.rid):
            #print "remove", self
            del Command.lut[self.rid]
            self.done = True
            return True
        return False

    @staticmethod
    def on_reply(rid, info):
        cmd = Command.lut.get(rid)
        #print cmd, rid, info
        if cmd:
            cmd.reply(info)

    def on_timeout(self):
        print "timeout", self
        self.nak("timeout")

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
        sched.add(60, self.on_timeout)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        self.respond(info, "info")

class CrcReq(Command):

    def __init__(self, flash, rid, addr, size, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_crc_req, addr, size)
        sched.add(60, self.on_timeout)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        self.respond(info, "crc")

class WriteReq(Command):

    def __init__(self, flash, rid, addr, data, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_write, addr, data, False)
        sched.add(60, self.on_timeout)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        self.respond(info, "written")

#
#

class Handler:

    def __init__(self):
        self.f = Flash()
        self.dead = False

    @staticmethod
    def make_id():
        return Flash.make_id()

    def info_req(self, ack, nak=None):
        rid = Handler.make_id()
        n = nak or self.kill
        InfoReq(self.f, rid, ack=ack, nak=n)()

    def crc_req(self, ack, addr, size, nak=None):
        rid = Handler.make_id()
        n = nak or self.kill
        CrcReq(self.f, rid, addr, size, ack=ack, nak=n)()

    def write_req(self, ack, addr, data, nak=None):
        rid = Handler.make_id()
        n = nak or self.kill
        WriteReq(self.f, rid, addr, data, ack=ack, nak=n)()

    #

    def poll(self):
        info = self.f.read()
        if info:
            flash = info.get("flash")
            if flash:
                Command.on_reply(flash.get("rid"), flash)

    def kill(self, *args):
        print "KILL"
        self.dead = True

    def chain(self, ack):
        if ack:
            ack()
        else:
            print "Done"
            self.dead = True

    #
    #

    def write(self, start_addr, data, ack=None):

        c = CRC16()
        total_crc = c.calculate(data)
        print "writing", len(data), "bytes at", start_addr, "crc", "%04X" % total_crc

        def on_crc(info):
            #print "%04X" % info.get("crc")
            if info.get("crc") == total_crc:
                if info.get("addr") == start_addr:
                    if info.get("size") == len(data):
                        print "Verified %04X" % total_crc
                        self.chain(ack)
                        return
            print "Bad CRC", "%04" % info.get("crc"), "expected %04X" % total_crc
            self.dead = True

        def validate():
            self.crc_req(on_crc, start_addr, len(data))

        def make_ack(addr, size, crc, data):
            def on_written(info):
                if info.get("crc") == crc:
                    if info.get("addr") == addr:
                        if info.get("size") == size:
                            if requests.done():
                                validate()
                            return
                print "Error writing block, try again"
                def dave(*args):
                    raise Exception(*args)
                requests.run(self.write_req, on_written, addr, data, nak=dave)
            return on_written

        def on_info(info):
            blocks = info.get("blocks")
            size = info.get("size")
            packet = info.get("packet")
            total = blocks * size

            if not total:
                print "No Flash Found"
                self.dead = True
                return

            # chop the data up into packet sized blocks
            for addr in range(0, len(data), packet):
                d = data[addr:addr+packet]
                c = CRC16()
                crc = c.calculate(d)

                write_addr = addr + start_addr
                ack = make_ack(write_addr, len(d), crc, d)
                requests.run(self.write_req, ack, write_addr, d)

        requests = Chain()
        self.info_req(ack=on_info)

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-d", "--dev", dest="dev")
    p.add_option("-a", "--addr", dest="addr", type="int")
    p.add_option("-s", "--slot", dest="slot", type="int")
    p.add_option("-f", "--fname", dest="fname")
    p.add_option("-n", "--name", dest="name")
    p.add_option("-D", "--dir", dest="dir", action="store_true")
    p.add_option("-V", "--verify", dest="verify", action="store_true")
    p.add_option("-R", "--read", dest="read", action="store_true")
    p.add_option("-W", "--write", dest="write", action="store_true")

    opts, args = p.parse_args()

    handler = Handler()
    sched = Scheduler()

    time.sleep(2)

    #filename = "plot.py"
    #filename = "../arduino/sketchbook/blink/build-uno/blink.hex"
    #filename = "../arduino/sketchbook/radio_relay/build-uno/radio_relay.hex"
    filename = opts.fname

    if filename.endswith(".hex"):
        print "Convert from IntelHex"
        io = StringIO()
        convert(filename, io, False)
        data = io.getvalue()
    else:
        data = open(filename).read()

    addr = opts.addr
    slotno = opts.slot

    c = CRC16()
    crc = c.calculate(data)

    name = "slot_%03d" % slotno
    if slotno == 0:
        name = "BOOTDATA"
    if opts.name:
        name = opts.name

    if opts.write:
        assert addr, "Must set address"

        if not opts.slot is None:
            slot = struct.pack("<8sLHH", name, addr, len(data), crc)

            def on_written(*args):
                print "Writing slot", slotno, name
                handler.write(0, slot)
        else:
            on_written = None

        handler.write(addr, data, ack=on_written)

    while not handler.dead:
        handler.poll()
        sched.poll()

# FIN
