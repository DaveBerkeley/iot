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

    def __init__(self, dev, slot, copy, multiple=False):
        self.dev = dev
        self.slot = slot
        self.copy = copy
        self.multiple = multiple
        self.crc = None
        self.addr = None
        self.size = None
        self.dead = False
        self.record = None

    def request(self):
        self.dev.flash_fast_poll(1)
        self.dev.flash_info_req()

    def close(self):
        self.dev.flash_fast_poll(0)

    def copy_record(self, flash, slot, crc):
        print "Copy slot", flash["slot"], "to", slot
        name = flash["name"]
        if slot == 0:
            name = "BOOTDATA"
        self.dev.flash_record(slot, name, flash["addr"], flash["size"], crc)

    def on_record(self, flash):
        slot = flash["slot"]
        name = flash["name"]
        addr = flash["addr"]
        size = flash["size"]
        crc = flash["crc"]
        print "slot", slot, repr(name), 
        print "a=%d s=%d crc=%X" % (addr, size, crc),
        self.crc = crc
        self.addr = addr
        self.size = size
        self.dev.flash_crc_req(addr, size)
        self.record = flash

    def on_crc(self, flash):
        addr = flash["addr"]
        size = flash["size"]
        crc = flash["crc"]
        if (self.addr != addr) or (self.size != size):
            print "Wrong record",
            print "a=%d s=%d crc=%X" % (addr, size, crc)
        elif crc != self.crc:
            print "BAD CRC", 
            print "a=%d s=%d crc=%X" % (addr, size, crc)
        else:
            print "Okay"
            if not self.copy is None:
                self.copy_record(self.record, self.copy, crc)

        if self.multiple:
            self.slot += 1
            if self.slot < 8:
                self.dev.flash_record_req(self.slot)
                return
        self.dead = True

    def on_device(self, x):
        # MQTT callback function
        data = json.loads(x.payload)
        flash = data.get("flash")
        if not flash:
            return
        cmd = flash.get("cmd")
        if cmd == "info":
            size = flash["blocks"] * flash["size"]
            print "Flash found", size, "bytes"
            if size:
                self.dev.flash_record_req(self.slot)
            else:
                self.dead = True
        elif cmd == "record":
            self.on_record(flash)
        elif cmd == "crc":
            self.on_crc(flash)
        else:
            print flash

#
#   Flash Check main function.

def flash_check(devname, jsonserver, mqttserver, slot, copy=None, multiple=None):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    checker = Checker(dev, slot, copy, multiple=multiple)

    mqtt = broker.Broker("flash_check_" + time.ctime(), server=mqttserver)
    mqtt.subscribe("home/jeenet/" + devname, checker.on_device)

    mqtt.start()

    checker.request()

    while not checker.dead:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

    checker.close()

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
    p.add_option("-c", "--copy", dest="copy", type="int")
    p.add_option("-M", "--multiple", dest="multiple", action="store_true")

    opts, args = p.parse_args()

    jsonserver = opts.json
    mqttserver = opts.mqtt
    devname = opts.dev
    slot = opts.slot
    copy = opts.copy
    multiple = opts.multiple

    flash_check(devname, jsonserver, mqttserver, slot, copy, multiple)

# FIN
