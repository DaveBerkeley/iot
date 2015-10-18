#!/usr/bin/python

import sys

import jsonrpclib

from broker.core import DeviceProxy

#
#

host = "pi2"
server = jsonrpclib.Server('http://%s:8888' % host)

meter = DeviceProxy(server, "relaydev_7")

r = int(sys.argv[1])

meter.set_relay(r)

# FIN
