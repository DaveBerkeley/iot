#!/usr/bin/python

import sys
import json
import time
import optparse
from Queue import Queue

import jsonrpclib

from jeenet.system.core import DeviceProxy
import broker

#
#

next_rid = 0

def make_rid():
    global next_rid
    next_rid += 1
    return next_rid & 0xFF

#
#

class Checker:
    def __init__(self, x):
        pass

#
#   Decouple MQTT messages from the reader thread

class MqttReader:

    def __init__(self):
        self.q = Queue()
    def add(self, ident, info):
        print ident, info
        self.q.put((ident, info))
    def on_device(self, x):
        data = json.loads(x.payload)
        f = data.get("flash")
        if f:
            self.add("D", f)
    def on_gateway(self, x):
        data = json.loads(x.payload)
        p = data.get("packets")
        if p:
            self.add("G", p)

#
#   Flash Check main function.

def flash_check(devname, jsonserver, mqttserver):
    server = jsonrpclib.Server('http://%s:8888' % jsonserver)

    dev = DeviceProxy(server, devname)

    checker = Checker(dev)
    reader = MqttReader()

    mqtt = broker.Broker("flash_check_" + time.ctime(), server=mqttserver)
    mqtt.subscribe("home/jeenet/" + devname, reader.on_device)
    mqtt.subscribe("home/jeenet/gateway", reader.on_gateway)

    mqtt.start()

    #checker.request()

    while True: # not checker.dead:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

    #checker.close()

    mqtt.stop()
    mqtt.join()

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-j", "--json", dest="json", default="jeenet")
    p.add_option("-m", "--mqtt", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev")

    opts, args = p.parse_args()

    jsonserver = opts.json
    mqttserver = opts.mqtt
    devname = opts.dev

    flash_check(devname, jsonserver, mqttserver)

# FIN
