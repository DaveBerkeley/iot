#!/usr/bin/python

import sys
import time
import os
import optparse

import serial

#
#

def quoted(text):
    text = str(text)
    text = text.replace("[", "\[")
    return text

#
#

if __name__ == "__main__":

    dev = "/dev/ser"
    if not os.path.exists(dev):
        dev = "/dev/ttyUSB0"

    p = optparse.OptionParser()
    p.add_option("-r", "--reset", dest="reset", action="store_true")
    p.add_option("-w", "--write", dest="write")
    p.add_option("-d", "--dev", dest="dev", default=dev)

    opts, args = p.parse_args()

    con = serial.Serial(dev, 9600, timeout=5)

    if opts.reset:
        con.write('\nnode.restart()\n')
        time.sleep(4)
        con.write('\n')

    ofile = opts.write
    if ofile:
        con.write('file.open("%s","w")\n' % ofile)
        time.sleep(1)

    for fname in args:
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
