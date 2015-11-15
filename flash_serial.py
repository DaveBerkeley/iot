#!/usr/bin/python

import struct
import time

import serial

from jeenet.system.flash import FlashInterface
import jeenet.system.bencode as bencode

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
        self.s = serial.Serial(serdev, 57600, timeout=1, xonxoff=0, rtscts=0)
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
        print mid, `raw`, name, flags
        self.s.write(bencode.encode([ self.dev_id, raw ]))
        self.s.flush()

    def read(self):
 
        msg = ""
        while True:
            c = self.s.read(1)
            if not c:
                break
            msg += c
        print `msg`

        return self.parse(msg)

    def parse(self, msg):

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

fl = Flash()

time.sleep(2)

fl.flash_info_req(Flash.make_id())
#fl.flash_reboot(Flash.make_id())
#time.sleep(1)

print fl.read()

# FIN
