#!/usr/bin/python

import struct
import time
import sys

import serial

from jeenet.system.flash import FlashInterface, log
import jeenet.system.bencode as bencode

from flash_io import Scheduler

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
            pass
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
        self.ack = self.make_cb(ack)
        self.nak = self.make_cb(nak)

    def __call__(self):
        self.fn(self.rid, *self.args)

    @staticmethod
    def add(rid, cmd):
        Command.lut[rid] = cmd

    def remove(self):
        if Command.lut.get(self.rid):
            print "remove", self
            del Command.lut[self.rid]
            self.done = True
            return True
        return False

    @staticmethod
    def on_reply(rid, info):
        cmd = Command.lut.get(rid)
        print cmd, rid, info
        if cmd:
            cmd.reply(info)

    def timeout(self):
        print "timeout", self
        if self.remove():
            self.nak("timeout")

#
#

class InfoReq(Command):

    def __init__(self, flash, rid):
        Command.__init__(self, rid, flash.flash_info_req)
        sched.add(10, self.timeout)

    def reply(self, info):
        if info.get("cmd") == "info":
            print "ACK", info
            self.ack(info)
        else:
            self.nak(info)

#
#

class Handler:

    def __init__(self):
        self.f = Flash()

    @staticmethod
    def make_id():
        return Flash.make_id()

    def info_req(self):
        rid = Handler.make_id()
        c = InfoReq(self.f, rid)
        c()

    def poll(self):
        info = self.f.read()
        if info:
            flash = info.get("flash")
            if flash:
                Command.on_reply(flash.get("rid"), flash)

    def send(self):
        self.info_req()


#
#

handler = Handler()
sched = Scheduler()

time.sleep(2)

handler.send()

while True:
    ##print ".",
    #sys.stdout.flush()
    handler.poll()
    sched.poll()

# FIN
