#!/usr/bin/python -u

import time
import json

import serial

import mosquitto

#
#

def cmd(dev, state, txt):
    print `txt`
    s.write(txt)
    # get echo
    for c in txt:
        x = s.read()
        assert x == c, str(x)
    # get status
    txt = "R%d=%d\r\n" % (dev, state)
    for c in txt:
        x = s.read()
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

def on_message(x):
    data = json.loads(x.payload)
    print x.topic, data
    cmd = data["cmd"]
    fn = commands[cmd]
    fn(data["dev"], *data["args"])

#
#

s = serial.Serial("/dev/relays", baudrate=57600, timeout=1, rtscts=True)

mqtt = mosquitto.Mosquitto("relays")
mqtt.connect("mosquitto")

mqtt.on_message = on_message
mqtt.subscribe("home/relay")

time.sleep(3) # settle

#
#

while True:
    try:
        mqtt.loop()
    except KeyboardInterrupt:
        break

# FIN
