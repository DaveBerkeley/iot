#!/usr/bin/python

import sys
import json
import time

import jsonrpclib

from jeenet.system.core import DeviceProxy
import broker

#
#

class Checker:

    def __init__(self, dev, slot):
        self.dev = dev
        self.slot = slot
        self.crc = None
        self.addr = None
        self.size = None
        self.dead = False

    def request(self):
        self.dev.flash_record_req(self.slot)

    def on_device(self, x):
        data = json.loads(x.payload)
        flash = data.get("flash")
        if not flash:
            return
        cmd = flash.get("cmd")
        if cmd == "record":
            slot = flash["slot"]
            name = flash["name"]
            addr = flash["addr"]
            size = flash["size"]
            crc = flash["crc"]
            print "Got Record:", name, "slot", slot
            print "a=%d s=%d crc=%X" % (addr, size, crc)
            self.crc = crc
            self.addr = addr
            self.size = size
            self.dev.flash_crc_req(addr, size)
        elif cmd == "crc":
            addr = flash["addr"]
            size = flash["size"]
            crc = flash["crc"]
            if (self.addr != addr) or (self.size != size):
                print "Wrong record"
                print "a=%d s=%d crc=%X" % (addr, size, crc)
            elif crc != self.crc:
                print "BAD CRC"
                print "a=%d s=%d crc=%X" % (addr, size, crc)
            else:
                print "CRC Okay"
            self.dead = True

#
#

host = "localhost"
server = jsonrpclib.Server('http://%s:8888' % host)

dev = DeviceProxy(server, "relaydev_7")

slot = 0
mqttserver = "localhost"
devname = "relaydev_7"

checker = Checker(dev, slot)

mqtt = broker.Broker("flash_check_" + time.ctime(), server=mqttserver)
mqtt.subscribe("home/jeenet/" + devname, checker.on_device)

mqtt.start()

checker.request()

while not checker.dead:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

mqtt.stop()
mqtt.join()

# FIN
