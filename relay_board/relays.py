#!/usr/bin/python -u

import time

import serial

#
#

def cmd(dev, state, txt):
    print `txt`
    s.write(txt)
    # get echo
    for c in txt:
        x = s.read()
        assert x == c, str(x)
    # get status
    txt = "R%d=%d\r\n" % (dev, state)
    for c in txt:
        x = s.read()
        assert x == c, str(x)

#
#

s = serial.Serial("/dev/relays", baudrate=57600, timeout=1, rtscts=True)

time.sleep(3) # settle

print "start..."

#
#

for i in range(4):
    txt = "R%d=P%d\n" % (i, (i + 1) * 1000)
    cmd(i, 1, txt)

# FIN
