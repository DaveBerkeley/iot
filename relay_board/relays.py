#!/usr/bin/python -u

import time
import json

import serial

# https://pypi.python.org/pypi/paho-mqtt
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
    txt = "R%d=%s\r\n" % (dev, state)
    for c in txt:
        x = s.read()
        #print `x`, `c`
        # special case for toggle
        if c == 'X':
            x = c
        assert x == c, str(x)

def set(dev, state, expected=None):
    ex = expected
    if ex is None:
        ex = state
    cmd(dev, ex, "R%d=%s\n" % (dev, state))

def on(dev, *args):
    set(dev, 1)

def off(dev, *args):
    set(dev, 0)

def toggle(dev, *args):
    set(dev, 'T', expected='X')

def pulse(dev, period):
    set(dev, 'P' + str(period), expected=1)

commands = {
    "pulse"     : pulse,
    "on"        : on,
    "off"       : off,
    "toggle"    : toggle,
}

def on_mqtt(client, x, msg):
    data = json.loads(msg.payload)
    print msg.topic, data
    cmd = data["cmd"]
    fn = commands[cmd]
    args = data.get("args", [])
    fn(data["dev"], *args)

#
#

if __name__ == "__main__":

    s = serial.Serial("/dev/relays", baudrate=9600, timeout=1, rtscts=True)

    time.sleep(3) # settle

    # flush input
    while True:
        c = s.read()
        if not c:
            break
        print `c`
        time.sleep(0.5)

    mqtt = paho.Client("relays")
    mqtt.connect("mosquitto")

    mqtt.on_message = on_mqtt
    mqtt.subscribe("home/relay")

    print "start MQTT server"

    while True:
        try:
            mqtt.loop()
        except KeyboardInterrupt:
            break

# FIN
