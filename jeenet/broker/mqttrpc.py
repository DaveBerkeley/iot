#!/usr/bin/python

import time
import sys
import json

sys.path.insert(0, "..")

import broker

class MqttRpc:

    def __init__(self, server="mosquitto", topic="rpc/jeenet"):
        self.server = server
        self.topic = topic
        self.dead = False

    def on_msg(self, x):
        data = json.loads(x.payload)
        print data

    def run(self):
        mqtt = broker.Broker("rpc", server="mosquitto")
        mqtt.subscribe("rpc/jeenet", on_msg)

        mqtt.start()

        while not self.dead:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break

        mqtt.stop()
        mqtt.join()

    def kill(self):
        self.dead = True

# FIN
