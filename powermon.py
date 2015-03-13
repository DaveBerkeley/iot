#!/usr/bin/python

import time
import json

from broker import Broker

#
#

broker = Broker("myid", "mosquitto")

class Handler:

    def __init__(self):
        self.history = []

    def on_power(self, msg):
        data = json.loads(msg.payload)
        power = data["power"]
        self.history = [ power, ] + self.history[:2]
        if len(self.history) < 3:
            return
        diff = self.history[0] - self.history[-1]
        av = sum(self.history) / len(self.history)
        print int(av), [ int(x-av) for x in self.history ]

handler = Handler()

broker.subscribe("home/power", handler.on_power)

broker.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    broker.stop()

broker.join()

# FIN
