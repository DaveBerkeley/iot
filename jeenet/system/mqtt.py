
import time
import json
import os

import broker

from system.core import log

class Mqtt:

    def __init__(self, server, bus):
        log("MQTT", server)
        self.broker = bus
        self.dead = False
        self.mqtt = broker.Broker("mqtt" + str(os.getpid()), server)
        self.broker.register("gateway", self.on_event)

    def on_new_device(self, node, device):
        log("mqqt pub", node, device)
        self.broker.register(node, self.on_event)

    def on_event(self, node, info):
        info = info.copy()
        info["node"] = node
        log("MQTT", node, info)
        self.mqtt.send("home/jeenet/" + node, json.dumps(info))

    def kill(self):
        self.dead = True

    def run(self):
        #while not self.dead:
        #    time.sleep(1)
        pass

# FIN
