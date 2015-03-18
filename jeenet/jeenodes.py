#!/usr/bin/python -u

import time
import sys
import os
import datetime
import jsonrpclib
import socket
from threading import Thread

from broker.core import Device, Broker, Clock, log, run_threads, kill_threads, get_device, on_new_device
from broker.jeenet import JeeNodeDev, JeeNet, Gateway, message_info, Monitor
from broker.jsonrpc import JsonRpcServer
from broker.iot import IoT

from devices.pir import PirSensor
from devices.triac import Triac

verbose = True

#
#   Known device types

known_devices = {
    "Test Device v1.0" : PirSensor, # TODO
    "Triac Control v1.0" : Triac,
    "PIR Device v1.0" : PirSensor,
}

#
#   Handle unregistered Devices

class UnknownHandler:

    def __init__(self, network, broker):
        self.network = network
        self.broker = broker

    def add_device(self, node, data, info):
        print info
        dev = info.get("device")
        if not dev in known_devices:
            return False

        klass = known_devices[dev]
        name = "%s_%d" % (klass.__name__.lower(), node)
        log("Added device", name)
        d = klass(dev_id=node, node=name, network=self.network, broker=self.broker)
        d.description = dev
        d.on_net(node, data)
        return True

    def on_device(self, node, data):
        fields = [
            (JeeNodeDev.text_flag, "device", "p"),
        ]
        try:
            msg_id, flags, info = message_info(data, JeeNodeDev.fmt_header, fields)
        except TypeError:
            info = { "data" : `data` }

        if self.add_device(node, data, info):
            return

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
jeenet = JeeNet(dev=dev, verbose=verbose)
runners.append(jeenet)

broker = Broker(verbose=True)
runners.append(broker)

# Handle any unknown devices that message the gateway
unknown = UnknownHandler(jeenet, broker)
jeenet.register(-1, unknown.on_device)

clock = Clock(node="tick", broker=broker, period=0.1)
runners.append(clock)

js = JsonRpcServer(name="json", broker=broker, port=8888)
runners.append(js)

# Monitor handles pinging any nodes and monitoring if they are down
monitor = Monitor(node="monitor", broker=broker, period=10, dead_time=20)
runners.append(monitor)

iot = IoT(name="iot", broker=broker, server="klatu")
runners.append(iot)

# Need a way of adding devices to IoT reporting
def report_to_iot(node, dev):
    iot.forward(dev.node)

on_new_device(report_to_iot)

# construct the gateway device
gateway = Gateway(dev_id=31, node="gateway", network=jeenet, broker=broker, verbose=verbose)

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
