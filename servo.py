#!/usr/bin/python

import sys
import time
import json

import broker

import serial

#
#

s = serial.Serial("/dev/nano_2-1_1", 9600)

topic = sys.argv[1]
field = None

#topic = "uif/seek/1"
#topic = "node/gas/sector"

if topic == "home/power":
    field = "power"

def translate(p):
    return int(p)

def r_translate(p, minx, maxx):
    d = maxx - minx
    p = min(maxx, max(minx, p))
    p -= minx
    p /=  d
    p *= 180
    return int(p)

if topic == "home/power":
    def translate(p):
        return r_translate(p, -2500.0, 2500.0)

if topic == "node/gas/sector":
    def translate(p):
        return r_translate(p, 0.0, 64.0)

#
#

def on_msg(x):
    data = json.loads(x.payload)
    if field:
        data = data.get(field)
        if data is None:
            return
    p = translate(data)
    print data, p
    s.write(str(p) + "\r")

mqtt = broker.Broker("uif", server="mosquitto")
mqtt.subscribe(topic, on_msg)

mqtt.start()

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

mqtt.stop()
mqtt.join()

# FIN
