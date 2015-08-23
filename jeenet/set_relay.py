#!/usr/bin/python

import sys

import jsonrpclib

from broker.core import DeviceProxy

#
#

host = "rpi"
server = jsonrpclib.Server('http://%s:8888' % host)

meter = DeviceProxy(server, "relaydev_6")

r = int(sys.argv[1])

meter.set_relay(r)

# FIN
