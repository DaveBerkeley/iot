#!/usr/bin/python

import sys
import os
import datetime
import json
import optparse

from subprocess import Popen, PIPE

def hm2s(text):
    h, m = text.split(":")
    h, m = [ int(x) for x in [ h, m ] ]
    return (m*60) + (h*60*60)

p = optparse.OptionParser()
p.add_option("-f", "--field", dest="field")
p.add_option("-s", "--subtopic", dest="subtopic")
p.add_option("-d", "--day", dest="day")
p.add_option("-S", "--start", dest="start")
p.add_option("-E", "--end", dest="end")
p.add_option("-l", "--log", dest="log", default="iot")

opts, args = p.parse_args()    

base = "/usr/local/data/" + opts.log

day = opts.day
subtopic = opts.subtopic
field = opts.field

start, end = opts.start, opts.end
if start:
    start = hm2s(start)
if end:
    end = hm2s(end)

path = os.path.join(base, day + ".log")

opath = "/tmp/plot.csv" 
ofile = open(opath, "w")

#
#   Handlers for the different log files

def iot(line):
    return json.loads(line)

def gas(line):
    parts = line.split()
    hms = parts[0]
    hm = hms[:2], hms[2:4], hms[4:6]
    hm = ":".join(hm)
    d = {
        "subtopic"  : "gas",
        "time"      : "xxxx " + hm,
        "sector"    : parts[1],
        "rots"      : parts[2],
        "total"     : parts[3],
        "rate"      : parts[4],
    }
    return d

handler = {
    "iot" : iot,
    "gas" : gas,
}

fn = handler[opts.log]

#print path

for line in file(path):
    data = fn(line)
    if data.get("subtopic") != subtopic:
        if data.get("ipaddr") != subtopic:
            continue
    if data.get(field) is None:
        continue

    keys = [ "time", field ]
    tt = data["time"]
    ymd, hms = tt.split(" ")
    print >> ofile, hms,
    print >> ofile, data[field],
    print >> ofile

gnuplot = [
    "set xdata time",
    "set format x '%H:%M'",
    "set timefmt '%H:%M:%S'",
    "set ylabel '%s'" % field,
    "set xlabel 'time'",
    "set xtics rotate by -45",
    "set key off",
    "plot '%s' using 1:2 with lines, '%s' using 1:2 with points" % (opath, opath),
]

if start:
    if end:
        gnuplot.insert(0, "set xrange[%s:%s]" % (start, end))
    else:
        gnuplot.insert(0, "set xrange[%s:]" % start)
elif end:
    gnuplot.insert(0, "set xrange[:%s]" % end)

cmd = "gnuplot --persist"
p = Popen(cmd, shell=True, stdin=PIPE)

for line in gnuplot:
    print >>p.stdin, line

# FIN
