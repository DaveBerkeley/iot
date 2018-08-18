#!/usr/bin/python -u

import os
import time
import threading

# http://pyserial.sourceforge.net/
import serial

import broker

dead = False

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
        self.path = path
        self.s = None

    def monitor(self):
        self.s = init_serial(self.path)

        while not dead:
            try:
                line = self.s.readline()
            except Exception, ex:
                log("exception", str(ex))
                time.sleep(10)
                self.s = init_serial(self.path)
                continue

            if line:
                log(line.strip())

    def on_mqtt(self, x):
        log("x", x.payload)
        # validate!
        self.s.write(x.payload + "\r\n")

#
#

if __name__ == "__main__":
    mqtt = broker.Broker("usb_control" + str(os.getpid()), server="mosquitto")

    def wrap(fn):
        def f(line):
            try:
                fn(line)
            except Exception as ex:
                log("Exception", str(fn), str(ex))
        return f

    usb = UsbControl("/dev/ttyUSB0")

    mqtt.subscribe("home/usb/0", wrap(usb.on_mqtt))

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
