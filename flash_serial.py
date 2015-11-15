#!/usr/bin/python

import struct
import time
import sys

import serial

from jeenet.system.flash import FlashInterface, log
import jeenet.system.bencode as bencode

from flash_io import Scheduler, Chain

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

#from flash_io import Command

#
#

class InfoReq(Command):

    def __init__(self, flash, rid, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_info_req)
        sched.add(10, self.on_timeout)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        if info.get("cmd") == "info":
            self.ack(info)
        else:
            self.nak(info)

class CrcReq(Command):

    def __init__(self, flash, rid, addr, size, ack=None, nak=None):
        Command.__init__(self, rid, flash.flash_crc_req, addr, size)
        sched.add(10, self.on_timeout)
        self.set_ack_nak(ack, nak)

    def reply(self, info):
        if info.get("cmd") == "crc":
            self.ack(info)
        else:
            self.nak(info)

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

    def poll(self):
        info = self.f.read()
        if info:
            flash = info.get("flash")
            if flash:
                Command.on_reply(flash.get("rid"), flash)

    def kill(self, *args):
        print "KILL"
        self.dead = True

    def send(self):

        def on_crc(info):
            print info
            self.dead = True

        def on_info(info):
            blocks = info.get("blocks")
            size = info.get("size")
            total = blocks * size
            print "Got", total, info
            if not total:
                self.dead = True
            else:
                requests.run(self.crc_req, on_crc, 0, 16000)

        requests = Chain()
        self.info_req(ack=on_info)

#
#

handler = Handler()
sched = Scheduler()

time.sleep(2)

handler.send()

while not handler.dead:
    handler.poll()
    sched.poll()

# FIN
