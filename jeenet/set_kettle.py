#!/usr/bin/python

import time
import sys
import json

import jsonrpclib

from broker.core import DeviceProxy

host = "rpi"
server = jsonrpclib.Server('http://%s:8888' % host)

meter = DeviceProxy(server, "triac_4")

#meter.set_mode(0)

def set_power(p):
    print "set", p
    meter.power = p
    meter.set_power(p)

def auto(burn):
    import paho.mqtt.client as paho    

    mqtt = paho.Client("me")
    mqtt.connect("mosquitto")

    def on_message(a, b, x):
        data = json.loads(x.payload)
        print x.topic, data
        if x.topic == "home/power":
            if data["power"] > burn:
                if meter.power > 0:
                    set_power(meter.power - 1)
            else:
                if meter.power < 100:
                    set_power(meter.power + 1)

    mqtt.on_message = on_message
    mqtt.subscribe("home/jeenet/kettle")
    mqtt.subscribe("home/power")
    mqtt.subscribe("rivers/#")

    set_power(0)

    while True:
        try:
            mqtt.loop()
        except KeyboardInterrupt:
            break

    set_power(0)


#
#

if len(sys.argv) > 1:
    if sys.argv[1] == "auto":
        watts = 0
        if len(sys.argv) > 2:
            watts = int(sys.argv[2], 10)
        auto(watts)
    else:
        p = int(sys.argv[1], 10)
        meter.set_power(p)
else:
    while True:
        for i in range(101):
            print "set power", i
            meter.set_power(i)
            time.sleep(1)
        break

# FIN
