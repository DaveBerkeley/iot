#!/usr/bin/python

import sys
import time

import serial

#
#

def quoted(text):
    text = str(text)
    text = text.replace("[", "\[")
    return text

#
#

con = serial.Serial("/dev/ttyUSB0", 9600, timeout=5)

fname = sys.argv[1]

if len(sys.argv) > 2:
    ofile = sys.argv[2]
else:
    ofile = None

if ofile:
    con.write('file.open("%s","w")\n' % ofile)

for line in file(fname):
    print `line`
    if ofile:
        line = line.strip()
        line = 'file.writeline([[' + quoted(line) + ']])\n'
        con.write(line)
    else:
        con.write(line)
    time.sleep(0.2)

if ofile:
    con.write('file.close()\n')

# FIN
