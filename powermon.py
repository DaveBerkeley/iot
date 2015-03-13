#!/usr/bin/python

import time
import json

from broker import Broker

#
#

broker = Broker("myid", "mosquitto")

def on_power(msg):
    data = json.loads(msg.payload)
    print data["power"]

broker.subscribe("home/power", on_power)

broker.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    broker.stop()

broker.join()

# FIN
