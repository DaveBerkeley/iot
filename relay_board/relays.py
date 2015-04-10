#!/usr/bin/python -u

import os
import time
import json

# http://pyserial.sourceforge.net/
import serial

# https://pypi.python.org/pypi/paho-mqtt
import paho.mqtt.client as paho

def log(*args):
    print time.strftime("%y/%m/%d %H:%M:%S :"), 
    for arg in args:
        print arg,
    print

#
#

def cmd(dev, state, txt):
    #print `txt`
    s.write(txt)
    # get echo
    for c in txt:
        x = s.read()
        assert x == c, str(x)
    # get status
    txt = "R%d=%s\r\n" % (dev, state)
    for c in txt:
        x = s.read()
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

def npulse(dev, period):
    set(dev, 'N' + str(period), expected=0)

#   Command LUT
#

commands = {
    "pulse"     : pulse,
    "npulse"    : npulse,
    "on"        : on,
    "off"       : off,
    "toggle"    : toggle,
}

#   MQTT on_message callback
#

def on_mqtt(client, x, msg):
    global s
    try:
        if s is None:
            s = init_serial()
        data = json.loads(msg.payload)
        log(msg.topic, data)
        cmd = data["cmd"]
        fn = commands[cmd]
        args = data.get("args", [])
        fn(data["dev"], *args)
    except (serial.serialutil.SerialException, OSError), ex:
        # shut down the serial port and reconnect
        log(str(ex))
        s = None

#
#

def init_serial():
    log("open serial '%s'" % serial_dev)
    s = serial.Serial(serial_dev, baudrate=9600, timeout=1, rtscts=True)

    time.sleep(3) # settle

    # flush input
    while True:
        c = s.read()
        if not c:
            break
        log(`c`)
        time.sleep(0.5)

    log("serial opened")
    return s

#
#

s = None # serial port

names = [
    "/dev/relays",
    "/dev/ttyACM0",
    "/dev/ttyUSB0",
]

for serial_dev in names:
    if os.path.exists(serial_dev):
        break

if __name__ == "__main__":

    s = init_serial()

    mqtt = paho.Client("relays")
    mqtt.connect("mosquitto")

    mqtt.on_message = on_mqtt
    mqtt.subscribe("home/relay")

    log("start MQTT server")

    mqtt.loop_forever()

# FIN
