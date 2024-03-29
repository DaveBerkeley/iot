#!/usr/bin/python

import sys
import time
import optparse
import json
import threading

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

def init_serial(dev):
    return serial.Serial(dev, 9600, timeout=1)

def command(text):
    global s
    log("cmd", text)
    s.write(text + "\r\n")

dead = False

class Motor:

    def __init__(self):
        self.rsp = "X"
        self.last = None
    def response(self, text):
        if text != self.last:
            log(text)
            self.last = text
        self.rsp = text
    def ready(self):
        return sefl.rsp[0] == 'R'

    def listen(self):
        global s
        text = ""
        while not dead:
            t = s.read(1)
            if not t:
                continue
            text += t
            if not t in "\n":
                continue
            text, rsp = "", text.strip()
            self.response(rsp)

motor = Motor()

def on_mqtt(client, x, msg):
    global s
    try:
        if s is None:
            s = init_serial()
        #log(msg.payload)
        data = json.loads(msg.payload)
        log(msg.topic, data)
        cmd = data["cmd"]
        value = data.get("value", "0")
        text = str(cmd + str(int(value)))
        command(text)
        #log("done")
    except (serial.serialutil.SerialException, OSError), ex:
        # shut down the serial port and reconnect
        log(str(ex), msg.payload)
        s = None

#
#

if __name__ == "__main__":
    p = optparse.OptionParser()
    p.add_option("-s", "--serial", dest="serial", type="str", default='/dev/arduino')
    p.add_option("-m", "--mqtt-server", dest="mqtt", default="mosquitto")
    p.add_option("-d", "--dev", dest="dev", type="int", default=0)
    p.add_option("-r", "--range", dest="range", type="int", default=4096)
    p.add_option("-t", "--topic", dest="topic", default="home/stepper/0")

    opts, args = p.parse_args()

    serial_dev = opts.serial
    base_dev = opts.dev
    s = init_serial(serial_dev)

    thread = threading.Thread(target=motor.listen)
    thread.start()

    # flush the stepper's command buffer
    time.sleep(1);
    command("")
    time.sleep(1);
    command("S%d" % opts.range);
    time.sleep(1);

    name = time.strftime("stepper_%Y%m%d%H%M")
    mqtt = paho.Client(name)
    mqtt.connect(opts.mqtt)

    mqtt.on_message = on_mqtt
    log("subscribe", opts.topic)
    mqtt.subscribe(opts.topic)

    log("start MQTT client '%s'" % name)

    try:
        mqtt.loop_forever()
    except KeyboardInterrupt:
        pass

    dead = True
    thread.join()

# FIN
