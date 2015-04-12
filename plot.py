#!/usr/bin/python

import sys
import os
import datetime
import json

base = "/usr/local/data/iot"

day = sys.argv[1]
subtopic = sys.argv[2]
field = sys.argv[3]

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
    "plot '%s' using 1:2 with lines" % opath,
]

for line in gnuplot:
    print line

# FIN
