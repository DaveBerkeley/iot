#!/usr/bin/python

import time
import sys
import json
import os

# add path to broker library
sys.path.insert(0, "..")
import broker

from core import Device, log, get_device

#
#

class MqttRpc:

    def __init__(self, server, topic):
        self.server = server
        self.topic = topic
        self.dead = False

    def on_msg(self, x):
        try:
            data = json.loads(x.payload)
            log("mqtt", data)
            dev_name = data.get("device")
            fn_name = data.get("fn")
            args = data.get("args", [])
            log("mqtt", dev_name, fn_name, args)
            
            dev = get_device(dev_name)
            log("found device", dev)
            if not dev:
                return
            if not fn_name in dev.api:
                raise Exception("no function '%s'" % fn_name)
            fn = getattr(dev, fn_name)
            fn(*args)
        except Exception, ex:
            log("mqtt", str(ex))

    def run(self):
        log("mqtt starting", self.server, self.topic)
        mqtt = broker.Broker("rpc" + str(os.getpid()), self.server)
        mqtt.subscribe(self.topic, self.on_msg)

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

#
#

if __name__ == "__main__":
    rpc = MqttRpc("mosquitto", "rpc/jeenet")
    rpc.run()

# FIN
