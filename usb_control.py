#!/usr/bin/python -u

import os
import time
import threading
import argparse
import Queue

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

class UsbControl:

    def __init__(self, path):
        self.dead = False
        self.path = path
        self.s = init_serial(self.path)
        self.queue = Queue.Queue()

        # wait for start
        usb = 'USB Control v 1.0'
        while True:
            line = self.s.readline()
            log("start", `line`)
            if line.startswith(usb):
                break

        self.state = ['X'] * 7
        self.set('S', "0123456")
        #time.sleep(1)
        self.state = ['X'] * 7
        self.set('S', "0123456")
        #time.sleep(1)

    def change(self, idx, state):
        if state == '1':
            # set it anyway
            return idx
        diff = ""
        for x in map(int, idx):
            if self.state[x] != state:
                diff += chr(x + ord('0'))
        return diff

    def set_state(self, idx, state):
        for x in map(int, idx):
            self.state[x] = state

    def get_busy(self):
        self.s.write("?\r\n")
        line = self.s.readline()
        idx = ""
        for i, c in enumerate(line.strip()):
            if c == 'X':
                idx += chr(i + ord('0'))
        return idx

    def overlap(self, a, b):
        r = ""
        for c in a:
            if c in b:
                r += c
        return r

    def set(self, c, idx):
        log("set", c, idx)
        if c == 'S':
            s = '1'
        elif c == 'R':
            s = '0'
        else:
            raise Exception(("set", c))
        idx = self.change(idx, s)
        if not idx:
            return

        # TODO : wait for idx not busy
        while True:
            busy = self.get_busy()
            if self.overlap(busy, idx):
                log("busy", busy)
                time.sleep(0.1)
                continue

            log("cmd", c, idx)
            self.s.write("%s%s\r\n" % (c, idx))
            # todo : wait for okay
            line = self.s.readline()
            if line.strip() == 'okay':
                self.set_state(idx, s)
            else:
                log("got set", `line`)
            break

    def monitor(self):
        while not self.dead:

            # todo : wait for started
            if not self.queue.empty():
                cmd, idx = self.queue.get()
                self.set(cmd, idx)

            try:
                line = self.s.readline()
            except Exception, ex:
                log("exception", str(ex))
                time.sleep(10)
                self.s = init_serial(self.path)
                continue

            if not line:
                continue

            if line:
                log(line.strip())

    def on_mqtt(self, x):
        #log("on_mqtt", x.payload)
        # validate!
        line = x.payload
        cmd, idx = line[0], line[1:]
        self.queue.put((cmd, idx))

#
#

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Interface underfloor nano to MQTT')
    parser.add_argument('--dev', dest='dev', default='/dev/ttyUSB0')
    parser.add_argument('--mqtt', dest='mqtt', default='mosquitto')
    parser.add_argument('--topic', dest='topic', default='home/usb/0')
    
    args = parser.parse_args()

    mqtt = broker.Broker("usb_control" + str(os.getpid()), server=args.mqtt)

    def wrap(fn):
        def f(line):
            try:
                fn(line)
            except Exception as ex:
                log("Exception", str(fn), str(ex))
        return f

    usb = UsbControl(args.dev)

    mqtt.subscribe(args.topic, wrap(usb.on_mqtt))

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
