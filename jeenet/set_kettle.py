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
    p = int(p)
    print "set", p
    if p > 100:
        p = 100
    elif p < 0:
        p = 0
    meter.power = p
    meter.set_power(p)

#
#

class PID:

    def __init__(self, p, i, setpoint=0, setter=None):
        self.p = p
        self.i = i
        self.setpoint = setpoint
        self.level = 0
        self.sum_error = 0
        self.setter = setter

    def tick(self, d):
        error = self.setpoint - d
        p = (self.p * error) + self.sum_error
        print d, error, p, self.sum_error
        self.setter(p)
        self.sum_error = ((1 - self.i) * self.sum_error) + (self.i * error)

#
#

pid = PID(0.01, 0.01, setpoint=-10, setter=set_power)

def auto():
    import paho.mqtt.client as paho    

    mqtt = paho.Client("me")
    mqtt.connect("mosquitto")

    dead = False

    def on_message(a, b, x):
        try:
            data = json.loads(x.payload)
            print x.topic, data
            if x.topic == "home/power":
                pid.tick(data["power"])
        except Exception, ex:
            print str(ex)
            dead = True

    mqtt.on_message = on_message
    mqtt.subscribe("home/power")

    set_power(0)

    while not dead:
        try:
            mqtt.loop()
        except KeyboardInterrupt:
            break

    set_power(0)


#
#

if sys.argv[1] == "auto":
    auto()
else:
    p = int(sys.argv[1], 10)
    meter.set_power(p)

# FIN
