#!/usr/bin/python -u

import os
import time
import threading
import json
import argparse

# http://pyserial.sourceforge.net/
import serial

import broker

#
#

lock = threading.Lock()

def log(*args):
    with lock:
        print time.strftime("%y/%m/%d %H:%M:%S :"), 
        for arg in args:
            print arg,
        print

#
#

def init_serial(path):
    log("open serial '%s'" % path)
    s = serial.Serial(path, baudrate=9600, timeout=1, rtscts=True)
    log("serial opened", path)
    return s

#
#

class Underfloor:

    lut = { 
        'd' : 'distance',
        'h' : 'humidity',
        'f' : 'fan',
        'p' : 'pump',
        't' : 'temp',
    }

    slow = 'h', 't'

    def __init__(self, broker, topic, path, period=10):
        self.dead = False
        self.path = path
        self.s = init_serial(self.path)
        self.data = {}
        self.idx = 0
        self.period = period
        self.broker = broker
        self.last = None
        self.last_time = 0
        self.topic = topic

    def parse(self, line):
        d = {}
        d.update(self.data)
        parts = line.split()
        for part in parts:
            key, value = part.split('=')
            if key in self.slow:
                if self.idx != 0:
                    continue
            d[self.lut[key]] = float(value)

        self.idx += 1
        if self.idx >= self.period:
            self.idx = 0

        self.data.update(d)
        return d

    def monitor(self):
        while not self.dead:
            try:
                line = self.s.readline()
            except Exception, ex:
                log("exception", str(ex))
                time.sleep(10)
                self.s = init_serial(self.path)
                continue

            if not line:
                continue

            log(line.strip())

            try:
                d = self.parse(line)
            except Exception as ex:
                log("exception", str(ex))
                continue

            now = time.time()
            if d == self.last:
                if (self.last_time + self.period) > now:
                    continue

            self.last_time = now
            self.last = d
            self.broker.send(self.topic, json.dumps(d))

    def on_fan(self, x):
        log("on_fan", x.payload)
        # validate!
        assert x.payload[0] == 'f', x.payload
        self.s.write(x.payload + '\r\n')

    def on_pump(self, x):
        log("on_pump", x.payload)
        # validate!
        assert x.payload[0] == 'p', x.payload
        self.s.write(x.payload + '\r\n')

#
#

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Interface underfloor nano to MQTT')
    parser.add_argument('--dev', dest='dev', default='/dev/underfloor')
    parser.add_argument('--mqtt', dest='mqtt', default='mosquitto')
    parser.add_argument('--topic', dest='topic', default='home/underfloor')
    parser.add_argument('--fan', dest='fan', default='home/fan/0')
    parser.add_argument('--pump', dest='pump', default='home/pump/0')

    args = parser.parse_args()

    mqtt = broker.Broker("underfloor" + str(os.getpid()), server=args.mqtt)

    def wrap(fn):
        def f(line):
            try:
                fn(line)
            except Exception as ex:
                log("Exception", str(fn), str(ex))
        return f

    usb = Underfloor(mqtt, args.topic, args.dev)

    mqtt.subscribe(args.fan, wrap(usb.on_fan))
    mqtt.subscribe(args.pump, wrap(usb.on_pump))

    try:
        mqtt.start()
        usb.monitor()
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        log("exception", str(ex))

    mqtt.stop()
    mqtt.join()

# FIN