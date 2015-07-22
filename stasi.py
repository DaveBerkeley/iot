#!/usr/bin/python

import time
import datetime
import json

import broker

# Private pir_ip and device_mac data
from stasi_conf import ip2loc, mac2dev

#
#

def log(*args):
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print

#

class Handler:

    def on_dhcp(self, x):
        data = json.loads(x.payload)
        mac = data.get("mac")
        log("DHCP", mac, mac2dev.get(mac))

    def on_pir(self, x):
        data = json.loads(x.payload)
        ip = data.get("ipaddr")
        where = ip2loc.get(ip, "Unknown")
        log("pir", where)

handler = Handler()

mqtt = broker.Broker("stasi", server="mosquitto")
mqtt.subscribe("home/net/dhcp", handler.on_dhcp)
mqtt.subscribe("home/pir", handler.on_pir)

mqtt.start()

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        log("irq")
        break

mqtt.stop()
mqtt.join()

# FIN
