#!/usr/bin/python -u

import time
import sys
import os
import datetime
import jsonrpclib
import socket
from threading import Thread

from broker.core import Device, Broker, Clock, log, run_threads, kill_threads, get_device
from broker.jeenet import JeeNodeDev, JeeNet, Gateway, message_info, Monitor
from broker.jsonrpc import JsonRpcServer
from broker.iot import IoT

from devices.pir import PirSensor
from devices.triac import Triac

verbose = True

#
#   Handle unregistered Devices

class UnknownHandler:

    def __init__(self, network, broker):
        self.network = network
        self.broker = broker
        self.seen = {}

    def on_device(self, node, data):
        fields = [
            (JeeNodeDev.text_flag, "device", "p"),
        ]
        try:
            msg_id, flags, info = message_info(data, JeeNodeDev.fmt_header, fields)
            # Could send an ack here, but probably best not to
        except TypeError:
            info = { "data" : `data` }

        if self.seen.get(node):
            return
        self.seen[node] = True

        info["error"] = "unknown device"
        info["why"] = info.get("device", "message received")
        self.broker.send("unknown_node_%d" % node, info)

#
#

if len(sys.argv) > 1:
    dev = sys.argv[1]
else:
    arduino = "/dev/arduino"
    if os.path.exists(arduino):
        dev = arduino
    else:
        dev = "/dev/ttyACM0"

runners = []

# make a jeenet reader
jeenet = JeeNet(dev=dev, verbose=True)
runners.append(jeenet)

broker = Broker(verbose=True)
runners.append(broker)

unknown = UnknownHandler(jeenet, broker)
jeenet.register(-1, unknown.on_device)

clock = Clock(node="tick", broker=broker, period=0.1)
runners.append(clock)

js = JsonRpcServer(name="json", broker=broker, port=8888)
runners.append(js)

iot = IoT(name="iot", broker=broker, server="klatu")
runners.append(iot)
# Need a way of adding devices to IoT reporting
for dev in [ "kettle", "PIR", "gateway" ]:
    iot.forward(dev)

#
#

monitor = Monitor(node="monitor", broker=broker, period=10, dead_time=20)
runners.append(monitor)

# construct the devices from config
gateway = Gateway(dev_id=31, node="gateway", network=jeenet, broker=broker, verbose=verbose)

triac = Triac(dev_id=4, node="kettle", network=jeenet, broker=broker) # real power switch
#pir = PirSensor(dev_id=3, node="PIR", network=jeenet, broker=broker)

#Triac(dev_id=2, node="triac", network=jeenet, broker=broker)
#PirSensor(dev_id=2, node="test_pir", network=jeenet, broker=broker)

# open the networks
jeenet.open()
jeenet.reset()

# start the threads
threads = run_threads(runners)

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

log("killing ...")
kill_threads(threads)

# FIN
