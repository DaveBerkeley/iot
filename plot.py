#!/usr/bin/python

import sys
import os
import datetime
import json

def hm2s(text):
    h, m = text.split(":")
    h, m = [ int(x) for x in [ h, m ] ]
    return (m*60) + (h*60*60)


base = "/usr/local/data/iot"

day = sys.argv[1]
subtopic = sys.argv[2]
field = sys.argv[3]

start, end = None, None
if len(sys.argv) > 4:
    start = hm2s(sys.argv[4])
    if len(sys.argv) > 5:
        end = hm2s(sys.argv[5])

path = os.path.join(base, day + ".log")

opath = "/tmp/plot.csv" 
ofile = open(opath, "w")

#print path

for line in file(path):
    data = json.loads(line)
    if data.get("subtopic") != subtopic:
        continue
    if data.get(field) is None:
        continue
    #keys = sorted(data.keys())
    keys = [ "time", field ]
    tt = data["time"]
    ymd, hms = tt.split(" ")
    print >> ofile, hms,
    print >> ofile, data[field],
    print >> ofile

gnuplot = [
    "set xdata time",
    "set format x '%H:%M'",
    "set timefmt '%H:%MS'",
    "set xlabel '%s'" % field,
    "set ylabel 'time'",
    "set xtics rotate by -45",
    "set key off",
    "plot '%s' using 1:2 with lines smooth bezier" % opath,
]

if start:
    if end:
        gnuplot.insert(0, "set xrange[%s:%s]" % (start, end))
    else:
        gnuplot.insert(0, "set xrange[%s:]" % start)
elif end:
    gnuplot.insert(0, "set xrange[:%s]" % end)

for line in gnuplot:
    print line

# FIN
