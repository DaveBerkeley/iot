#!/usr/bin/python

import sys
import json
import time

import jsonrpclib

from jeenet.system.core import DeviceProxy
import broker

#
#

class Dead(Exception):
    pass

class Xfer:

    INFO, DEAD, WRITE = "INFO", "DEAD", "WRITE"

    def __init__(self, device, addr, data):
        self.device = device
        self.start_addr = addr
        self.data = data
        self.avail = None
        self.size = None
        self.retry_time = 10 # s
        self.set_state(self.INFO)

    def set_state(self, state):
        print "set_state", state
        if state == self.INFO:
            self.count = 0
            for i in range(8):
                self.device.flash_info_req()

        elif state == self.WRITE:
            self.init_write()

        self.state = state

    def poll(self):
        print "tick"
        if self.state == self.DEAD:
            raise Dead()
        elif self.state == self.INFO:
            self.count += 1
            if self.count >= 10:
                self.device.flash_info_req()
                self.count = 0
        elif self.state == self.WRITE:
            if self.avail > 1:
                self.write(self.avail - 1)

    def cmd_info(self, info):
        if self.state == self.INFO:
            print "cmd_info", info
            if info["blocks"] < 0:
                print "Not enough flash"
                self.set_state(self.DEAD)
            else:
                self.set_state("WRITE")

    def cmd_crc(self, info):
        print "crc", info
        addr = info.get("addr", -1)
        for block in self.blocks:
            if block.addr == addr:
                block.state = self.Block.DONE
                print "written", block
                break

        # Any blocks left?
        remaining = False
        for block in self.blocks:
            if not (block.state == self.Block.DONE):
                remaining = True
                break
        if not remaining:
            print "written all blocks"
            self.set_state(self.DEAD)

    class Block:
        SENDING, CHECKING, DONE = "SENDING", "CHECKING", "DONE"

        def __init__(self, addr, data):
            self.addr = addr
            self.data = data
            self.sent = 0
            self.state = self.SENDING
        def __repr__(self):
            return "Block(%d,%d,%s)" % (self.addr, len(self.data), self.state)

    def init_write(self):
        # self.start_addr, 
        print "init_write"
        self.blocks = []
        for addr in range(0, len(self.data), self.size):
            d = Xfer.Block(addr, data[addr:addr+self.size])
            self.blocks.append(d)
            #print d

    def send(self, block):
        block.sent = time.time()
        block.state = self.Block.SENDING
        print "send", block, self.avail
        self.device.flash_crc_req(block.addr, len(block.data))
        self.avail -= 1

    def write(self, avail):
        #print "write"
        blocks = []
        now = time.time()
        for block in self.blocks:
            if block.state in [ self.Block.DONE, self.Block.CHECKING ]:
                continue
            if block.state == self.Block.SENDING:
                if (block.sent + self.retry_time) > now:
                    continue
            blocks.append((block.sent, block))
        blocks.sort()
        #print blocks
        for _, block in blocks[:avail]:
            self.send(block)

    def on_avail(self, avail, size):
        print "on_avail", avail, size
        self.avail = avail
        # TODO : remove me
        self.size = 4 # size

        if self.state == self.WRITE:
            if avail > 1:
                self.write(avail)

    # MQTT handlers monitoring gateway and device data :

    def on_device(self, x):
        data = json.loads(x.payload)
        flash = data.get("flash")
        if not flash:
            return
        # TODO : something is mangling the JSON data
        flash = flash.replace("'", '"')
        flash = json.loads(flash)
        #print "msg", flash
        name = "cmd_" + flash.get("cmd")
        if not hasattr(self, name):
            print name,"not implemented"
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

data = "Hello world!"

xfer = Xfer(device, 0, data)

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
