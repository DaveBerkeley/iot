#!/usr/bin/python

import sys
import json
import time
import base64
import httplib

# https://github.com/joshmarshall/jsonrpclib
import jsonrpclib

# https://github.com/cristianav/PyCRC
from PyCRC.CRC16 import CRC16

from jeenet.system.core import DeviceProxy
import broker

#
#

class Dead(Exception):
    pass

#raise httplib.HTTPException()

class Xfer:

    INFO, DEAD, WRITE = "INFO", "DEAD", "WRITE"

    def __init__(self, device, addr, data):
        self.device = device
        self.start_addr = addr
        self.data = data
        self.avail = None
        self.size = None
        self.packet_size = None
        self.retry_time = 60 # s
        self.blocks = []
        self.progress = 0, 0
        self.set_state(self.INFO)


    class Block:
        SENDING, CHECKING = "SENDING", "CHECKING"

        def __init__(self, addr, size, data):
            self.addr = addr
            self.size = size
            self.data = data
            self.sent = 0
            self.crc = None
            self.state = self.SENDING

        def __repr__(self):
            return "Block(%d,%d,%s,%s)" % (
                    self.addr, len(self.data), 
                    self.state,
                    "%04X" % self.crc)

    def set_state(self, state):
        print "set_state", state
        if state == self.INFO:
            self.count = 0
            for i in range(8):
                try:
                    self.device.flash_info_req()
                except httplib.HTTPException:
                    break

        elif state == self.WRITE:
            self.init_write()

        self.state = state

    def find_block(self, addr):
        for block in self.blocks:
            if block.addr == addr:
                return block
        return None

    def find_block_idx(self, block):
        for i, b in enumerate(self.blocks):
            if b is block:
                return i
        return None

    def poll(self):
        print "tick", "%d/%d" % self.progress
        #if len(self.blocks) < 8:
        #    print self.blocks
        if self.state == self.DEAD:
            raise Dead()
        elif self.state == self.INFO:
            self.count += 1
            if self.count >= 10:
                try:
                    self.device.flash_info_req()
                except httplib.HTTPException:
                    pass
                self.count = 0
        elif self.state == self.WRITE:
            #if self.avail > 3:
            #    self.write(self.avail - 1)
            
            if len(self.blocks) == 0:
                print "Sent all Blocks"
                self.set_state(self.DEAD)

    # Message response handlers

    def cmd_info(self, info):
        if self.state == self.INFO:
            print "cmd_info", info
            self.packet_size = info.get("packet", 0)
            if info["blocks"] < 0:
                print "Not enough flash"
                self.set_state(self.DEAD)
            else:
                self.set_state(self.WRITE)

    def cmd_crc(self, info):
        crc = info.get("crc", 0)
        print "crc(%s,%s) %04X" % (info.get("addr"), info.get("size"), crc)
        addr = info.get("addr", -1)
        block = self.find_block(addr)
        if not block:
            print "Can't find block", addr
            return
        if block.crc != crc:
            print "Bad-CRC %04X" % crc, block
            block.state = self.Block.SENDING
        else:
            idx = self.find_block_idx(block)
            a, b = self.progress
            self.progress = a + 1, b
            del self.blocks[idx]
            print "written", block

    def cmd_written(self, info):
        print "cmd_written", info
        addr = info.get("addr", -1)
        block = self.find_block(addr)
        if not block:
            print "Unknown block", addr
            return
        try:
            self.device.flash_crc_req(block.addr, block.size)
            block.state = self.Block.CHECKING
            block.sent = time.time()
        except httplib.HTTPException:
            pass

    #

    def init_write(self):
        print "init_write"
        self.blocks = []
        size = min(self.size, self.packet_size)
        for addr in range(0, len(self.data), size):
            d = data[addr:addr+size]
            b64 = base64.b64encode(d)
            block = Xfer.Block(addr + self.start_addr, len(d), b64)
            c = CRC16()
            block.crc = c.calculate(d)
            self.blocks.append(block)
        self.progress = 0, len(self.blocks)

    def send(self, block):
        print "send", block, self.avail
        # do write
        try:
            self.device.flash_write(block.addr, block.data, True)            
            block.sent = time.time()
            block.state = self.Block.SENDING
        except httplib.HTTPException:
            pass
        self.avail -= 1

    def write(self, avail):
        #print "write"
        blocks = []
        now = time.time()
        for block in self.blocks:
            if block.state == self.Block.CHECKING:
                if (block.sent + self.retry_time) > now:
                    print "Timeout Checking", block
                    block.state = self.Block.SENDING

            if block.state == self.Block.SENDING:
                if (block.sent + self.retry_time) > now:
                    continue
            blocks.append((block.sent, block))
        blocks.sort() # in time order

        for _, block in blocks[:avail]:
            self.send(block)

    def on_avail(self, avail, size):
        print "on_avail", avail, size
        self.avail = avail
        self.size = size

        if self.state == self.WRITE:
            if avail > 5:
                self.write(avail-3)

    # MQTT handlers monitoring gateway and device data :

    def on_device(self, x):
        data = json.loads(x.payload)
        flash = data.get("flash")
        if not flash:
            return
        # TODO : something is mangling the JSON data
        flash = flash.replace("'", '"')
        flash = json.loads(flash)

        name = "cmd_" + flash.get("cmd")
        if not hasattr(self, name):
            print name,"not implemented"
            self.set_state(self.DEAD)
            return
        fn = getattr(self, name)
        fn(flash)

    def on_gateway(self, x):
        data = json.loads(x.payload)
        packets = data.get("packets")
        if not packets:
            return
        if not ((packets[0] == "(") and (packets[-1] == ")")):
            return
        packets = packets[1:-1]
        avail, size = [ int(x) for x in packets.replace(" ", "").split(",") ]
        self.on_avail(avail, size)

#
#

host = "pi2"
server = jsonrpclib.Server('http://%s:8888' % host)

device = DeviceProxy(server, "relaydev_7")

data = "Hello World!"

if len(sys.argv) > 1:
    name = sys.argv[1]
    f = open(name)
    data = f.read()

xfer = Xfer(device, 100 * 1024L, data)

mqtt = broker.Broker("uif", server="mosquitto")
mqtt.subscribe("home/jeenet/relaydev_7", xfer.on_device)
mqtt.subscribe("home/jeenet/gateway", xfer.on_gateway)

mqtt.start()

while True:
    try:
        time.sleep(1)
        xfer.poll()
    except (KeyboardInterrupt, Dead):
        break

mqtt.stop()
mqtt.join()

# FIN
