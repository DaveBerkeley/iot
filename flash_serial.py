#!/usr/bin/python

import struct

from jeenet.system.flash import FlashInterface

last_mid = 0;

def make_mid():
    global last_mid
    last_mid += 1
    if last_mid > 255:
        last_mid = 1
    return last_mid

class Flash(FlashInterface):

    api = []
    flash_flag = 0x0800
    ack_flag = 0x8000
    fmt_header = "<BBH"

    def __init__(self):
        self.dev_id = 1

    def make_raw(self, flags, fields, msg_id=None):
        # fields as [ (bit_mask, fmt, value), ... ] in binary order

        mid = msg_id or make_mid()
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

fl = Flash()

fl.flash_info_req(123)

# FIN
