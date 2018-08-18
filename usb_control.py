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

def monitor(name):
    path = '/dev/' + name
    global s
    s = init_serial(path)

    while not dead:
        try:
            line = s.readline()
        except Exception, ex:
            log("exception", str(ex))
            time.sleep(10)
            s = init_serial(path)
            continue

        if line:
            log(line.strip())


def on_mqtt(x):
    log("x", x.payload)
    # validate!
    s.write(x.payload + "\r\n")

#
#

if 1:
    mqtt = broker.Broker("thingspeak_" + str(os.getpid()), server="mosquitto")

    def wrap(fn):
        def f(line):
            try:
                fn(line)
            except Exception as ex:
                log("Exception", str(fn), str(ex))
        return f

    if 1:
        mqtt.subscribe("home/usb/0", wrap(on_mqtt))

    #mqtt.subscribe("home/gas", on_gas_msg)
    mqtt.start()

    try:
        monitor("ttyUSB0")
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        log("exception", str(ex))

    mqtt.stop()
    mqtt.join()

# FIN
