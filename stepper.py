#!/usr/bin/python

import sys
import time
import optparse
import json

import serial

# https://pypi.python.org/pypi/paho-mqtt
import paho.mqtt.client as paho

def log(*args):
    print time.strftime("%y/%m/%d %H:%M:%S :"), 
    for arg in args:
        print arg,
    print

dev = sys.argv[1]

"""
ser = serial.Serial(dev, 9600, timeout=1)

time.sleep(1);
ser.write("\r\n")
time.sleep(1);

ser.write("G1000\r\n")
time.sleep(5);

ser.write("G2000\r\n")

time.sleep(5)
"""

def init_serial(dev):
    return serial.Serial(dev, 9600, timeout=1)

def on_mqtt(client, x, msg):
    global s
    try:
        if s is None:
            s = init_serial()
        log(msg.payload)
        data = json.loads(msg.payload)
        log(msg.topic, data)
        cmd = data["cmd"]
        value = data.get("value", "")
        s.write(str(cmd + str(int(value)) + "\r\n"))
        #args = data.get("args", [])
        #dev = data["dev"] - base_dev
        #if 0 <= dev <= 3:
        #    fn(dev, *args)
    except (serial.serialutil.SerialException, OSError), ex:
        # shut down the serial port and reconnect
        log(str(ex))
        s = None

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-s", "--serial", dest="serial", type="str", default='/dev/arduino')
    p.add_option("-m", "--mqtt-server", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev", type="int", default=0)

    opts, args = p.parse_args()

    serial_dev = opts.serial
    base_dev = opts.dev
    s = init_serial(serial_dev)

    name = time.strftime("stepper_%Y%m%d%H%M")
    mqtt = paho.Client(name)
    mqtt.connect(opts.mqtt)

    mqtt.on_message = on_mqtt
    mqtt.subscribe("home/stepper/0")

    log("start MQTT client '%s'" % name)

    mqtt.loop_forever()

# FIN
