#!/usr/bin/python

import sys

import jsonrpclib

from broker.core import DeviceProxy

#
#

host = "pi2"
server = jsonrpclib.Server('http://%s:8888' % host)

meter = DeviceProxy(server, "relaydev_7")

meter.flash_req_info()

# FIN
