#!/usr/bin/python

import time

import serial

#
#

def log(*args):
    print time.strftime("%y/%m/%d %H:%M:%S :"), 
    for arg in args:
        print arg,
    print

#
#

serial_dev = "/dev/nano"

def init_serial():
    log("open serial '%s'" % serial_dev)
    s = serial.Serial(serial_dev, baudrate=9600, timeout=1, rtscts=True)
    log("serial opened")
    return s

#
#

s = init_serial()

while True:
    line = s.readline()
    if not line.endswith("\r\n"):
        continue
    parts = line.strip().split(",")
    d = {}
    for i in range(0, len(parts), 2):
        key, value = parts[i:i+2]
        d[key] = value
    print d

# FIN
