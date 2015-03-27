#!/usr/bin/python -u

import time
import json

import serial

import paho.mqtt.client as paho

#
#

def cmd(dev, state, txt):
    print `txt`
    s.write(txt)
    # get echo
    for c in txt:
        x = s.read()
        #print `x`, `c`
        assert x == c, str(x)
    # get status
    txt = "R%d=%d\r\n" % (dev, state)
    for c in txt:
        x = s.read()
        #print `x`, `c`
        assert x == c, str(x)

def set(dev, state, expected=None):
    ex = expected
    if ex is None:
        ex = state
    cmd(dev, ex, "R%d=%s\n" % (dev, state))

def on(dev):
    set(dev, 1)

def off(dev):
    set(dev, 0)

def toggle(dev):
    set(dev, 'T', expected=1)

def pulse(dev, period):
    set(dev, 'P' + str(period), expected=1)

commands = {
    "pulse" : pulse,
    "on" : on,
    "off" : off,
    "toggle" : toggle,
}

def on_message(client, x, msg):
    data = json.loads(msg.payload)
    print msg.topic, data
    cmd = data["cmd"]
    fn = commands[cmd]
    fn(data["dev"], *data["args"])

#
#

s = serial.Serial("/dev/relays", baudrate=9600, timeout=1, rtscts=True)

mqtt = paho.Client("relays")
mqtt.connect("mosquitto")

mqtt.on_message = on_message
mqtt.subscribe("home/relay")

time.sleep(3) # settle

#for i in range(4):
#    s.write("P%d=?\n" % i)

# flush input
while True:
    c = s.read()
    if not c:
        break
    print `c`
    time.sleep(0.5)

#
#



print "start MQTT server"

while True:
    try:
        mqtt.loop()
    except KeyboardInterrupt:
        break

# FIN
