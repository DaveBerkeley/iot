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

def on_msg(x):
    data = json.loads(x.payload)
    if data.get("subtopic") != "jeenet/testdev_1":
        return
    temp = float(data["temp"])
    print temp

mqtt = broker.Broker("bread", server="mosquitto")
mqtt.subscribe("home/jeenet/#", on_msg)

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
