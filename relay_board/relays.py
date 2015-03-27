#!/usr/bin/python -u

import time

import serial

s = serial.Serial("/dev/relays", baudrate=57600, timeout=1)

time.sleep(2) # settle

def cmd(dev, state, txt):
    s.write(txt)
    # get echo
    for c in txt:
        assert s.read() == c
    # get status
    txt = "R%d=%d\r\n" % (dev, state)
    for c in txt:
        assert s.read() == c

for i in range(4):
    txt = "R%d=P%d\n" % (i, (i + 1) * 1000)
    cmd(i, 1, txt)

# FIN
