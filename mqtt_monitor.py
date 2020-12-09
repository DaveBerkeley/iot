#!/usr/bin/python3

import time, datetime
import os
import sys
import json

import broker3 as broker

#
#

def log(*args):
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print(ymd + " " + hms[:-3], end='')
    for arg in args:
        print(' ', arg, end='')
    print('')

#
#

def wrap(fn):
    def f(line):
        try:
            fn(line)
        except Exception as ex:
            log("Exception", str(fn), str(ex))
    return f

#
#

filename = None
fout = None

def write(data):
    log(data)

    now = datetime.date.today()
    path = '/usr/local/data/mqtt/%04d/%02d/%02d.log' % (now.year, now.month, now.day)

    global filename, fout
    if path != filename:
        if fout:
            fout.close()
            fout = None
        filename = path
        dirname, _ = os.path.split(path)
        if not os.path.exists(dirname):
            log("makedir", dirname)
            if not debug:
               os.makedirs(dirname)

    if not debug:
        if not fout:
            fout = open(filename, "w")

        fout.write(data + '\n')
        fout.flush()

#
#

def tasmota(x):
    # expects eg. 'tele/tasmota_7552E7/SENSOR'
    parts = x.topic.split('/')
    assert parts[0] == 'tele', parts
    assert parts[1].startswith('tasmota_'), parts
    #if parts[2] != 'SENSOR':
    #    return
    device = parts[1]
    cmd = parts[2]
    try:
        data = json.loads(x.payload)
    except Exception:
        log("json error", x.topic, x.payload)
        return
    data['Device'] = device
    data['cmd'] = cmd
    write(json.dumps(data))

#
#

if __name__ == "__main__":

    debug = len(sys.argv) > 1

    mqtt = broker.Broker("mqtt_mon_" + str(os.getpid()), server="mosquitto")

    mqtt.subscribe('tele/#', wrap(tasmota))
    mqtt.start()

    while True:
        time.sleep(1)

    mqtt.stop()
    mqtt.join()

#   FIN
