#!/usr/bin/python -u

import time
import datetime
import json

import broker

def log(*args):
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print

#
#

class Handler:

    def __init__(self, temp, src, dev, duration):
        self.temp = temp
        self.src = src
        self.dev = dev
        self.duration = duration

    def on_msg(self, x):
        data = json.loads(x.payload)
        if data.get("subtopic") != self.src:
            return
        temp = float(data["temp"])
        log(temp)
        if temp < self.temp:
            self.pulse()

    def pulse(self):
        d = { 
            "dev" : self.dev, 
            "cmd" : "pulse", 
            "args" : [ self.duration, ],
        }
        j = json.dumps(d)
        mqtt.send("home/relay", j)

#
#

handler = Handler(27.0, "jeenet/testdev_1", 5, 11000)

mqtt = broker.Broker("bread", server="mosquitto")
mqtt.subscribe("home/jeenet/#", handler.on_msg)

mqtt.start()

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        log("irq")
        break

mqtt.stop()
mqtt.join()

# FIN
