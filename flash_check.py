#!/usr/bin/python

import sys
import json
import time
import optparse

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
        self.dev.flash_info_req()

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
            print "Got Record:", repr(name), "slot", slot
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
        elif cmd == "info":
            print "Flash found", flash["blocks"] * flash["size"], "bytes"
            self.dev.flash_record_req(self.slot)
        else:
            print flash

#
#   Flash Check main function.

def flash_check(devname, jsonserver, mqttserver, slot):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

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

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-j", "--json", dest="json", default="jeenet")
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev")
    p.add_option("-s", "--slot", dest="slot", type="int", default=0)

    opts, args = p.parse_args()

    jsonserver = opts.json
    mqttserver = opts.mqtt
    devname = opts.dev
    slot = opts.slot

    flash_check(devname, jsonserver, mqttserver, slot)

# FIN
