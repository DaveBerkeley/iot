#!/usr/bin/python

import time
import json

from broker import Broker

#
#

class Handler:

    def __init__(self):
        self.history = []
        self.size = 3

    def on_power(self, msg):
        data = json.loads(msg.payload)
        power = data["power"]
        self.process(power)

    def process(self, power):
        self.history = [ power, ] + self.history[:self.size-1]
        if len(self.history) < self.size:
            return
        diff = self.history[0] - self.history[-1]
        av = sum(self.history) / len(self.history)
        print int(av), 
        print [ int(x-av) for x in self.history ], 
        print [ int(self.history[0]), int(self.history[-1]) ],
        print int(self.history[0]) - int(self.history[-1])

#
#

broker = Broker("myid", "mosquitto")

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
