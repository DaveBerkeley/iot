#!/usr/bin/python -u

import time
import datetime
import traceback
import json
import sys
from threading import Lock, Thread

import broker

from thing_speak import ThingSpeak, keys

#
#

log_lock = Lock()

def log(*args):
    log_lock.acquire()
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print
    log_lock.release()

#   Run the send in a thread.
#   This avoids hanging the main process on error.

def execute(fn, key, **kwargs):
    def run():
        fn(key, **kwargs)
    thread = Thread(target=run)
    thread.start()

#
#

throttle = {}

def tx_data(tag, **kwargs):
    now = time.time()
    last = throttle.get(tag)

    if (last and ((last+16) > now)):
        return
    tx_info(tag, **kwargs)

def tx_cloud(tag, **kwargs):
    key = keys[tag]["write"]
    log("TX", tag, key, kwargs)
    try:
        execute(cloud.post, key, **kwargs)
    except Exception, ex:
        #traceback.print_stack(sys.stdout)
        log(str(ex))

def tx_info(tag, info):
    log("TXTX", tag, info)

#
#

topics = {
    "gateway" : [ "temp", ],
    "humiditydev_2" : [ "humidity", "temp" ],
    "voltagedev_9" : [ "temp" ],
    #"relaydev_7"
}

def on_jeenet_msg(x):
    data = json.loads(x.payload)

    topic = x.topic.split("/")[-1]
    #log(data, topic)

    fields = topics.get(topic)
    if not fields:
        log("No fields for", topic)
        log(topic, fields, data)
        return

    d = {}
    for i, field in enumerate(fields):
        value = data.get(field)
        if not value is None:
            name = "field" + str(i+1)
            d[name] = value

    if len(d):
        tx_cloud(topic, **d)

#
#

last_net = {}

def on_net_msg(x):
    data = json.loads(x.payload)
    info = []
    if data.get("host") == "klatu":
        t0 = data.get("temp_0")
        t1 = data.get("temp_1")
        rx = data.get("rx")
        tx = data.get("tx")
        if (t0 is None) or (t1 is None):
            return
        if (rx is None) or (tx is None):
            return
        info.append(( str("klatu_0"), t0 ))
        info.append(( str("klatu_1"), t1 ))

        info.append(( str("klatu_rx"), rx ))
        info.append(( str("klatu_tx"), tx ))

        def delta(name, value):
            last = last_net.get(name)
            if not last is None:
                info.append(( str(name + "_d"), str(int(value) - int(last) )))

        delta("klatu_rx", rx)
        delta("klatu_tx", tx)

        for key in data.keys():
            if key.startswith("load_"):
                num = key[len("load_"):]
                info.append(( str("klatu_load_" + num), 100.0 * float(data[key])))

        for field, value in info:
            #print field, value
            last_net[field] = value

        tx_info("klatu_temp", info)

#
#

def on_pressure_msg(x):
    data = json.loads(x.payload)
    pressure = data["p"]
    sea = data["sea"]
    tx_cloud("barometer", field1=pressure, field2=sea)

#
#


def ip_2_mac(ip):
    # Lookup the MAC address in ARP table
    f = open("/proc/net/arp")
    for line in f:
        parts = line.split()
        if parts[0] == ip:
            return parts[3]
    return None

snoopie_lut = {
    # Hard code the known MAC Addresses
    '18:fe:34:9c:65:20' : 'snoopie_04', # Front room
    '18:fe:34:9c:65:5c' : 'snoopie_05', # Office
    '18:fe:34:9c:56:d0' : 'snoopie_06', # Green Box
    '18:fe:34:9c:56:bd' : 'snoopie_07',
    '18:fe:34:9c:56:cc' : 'snoopie_08', # Back room
    '18:fe:34:9c:56:ca' : 'snoopie_09', # Front bedroom
}

def on_home_msg(x):
    data = json.loads(x.payload)
    # TODO : make this smarter!
    ip = data.get("ipaddr")
    mac = ip_2_mac(ip)
    tag = snoopie_lut.get(mac)
    if tag is None:
        return
    #log("TAG", tag, mac)

    temp = data.get("temp")
    if not temp is None:
        tx_cloud(tag, field1=temp)

#
#

def on_gas_msg(x):
    data = json.loads(x.payload)
    info = ( 
        ( "gas_m3", 1000 * float(data["m3"]), ), 
        ( "gas_sector", data["sector"], ), 
        ( "gas_rate", 1000000 * float(data["rate"]), ), 
        ( "gas_rot", float(data["rots"]), ), 
    )
    tx_info("gas", info)

#
#

def on_dust_msg(x):
    data = json.loads(x.payload)
    dust = data["dust"]
    dust_5 = data["dust_5"]
    dust_10 = data["dust_10"]
    tx_cloud("dust", field1=dust, field2=dust_5, field3=dust_10)

#
#

if len(sys.argv) > 1:
    class Dummy:
        def post(self, key, **kwargs):
            log("put", key, kwargs)

    cloud = Dummy()
else:
    cloud = ThingSpeak()

#
#

mqtt = broker.Broker("xively", server="mosquitto")
mqtt.subscribe("home/jeenet/#", on_jeenet_msg)
#mqtt.subscribe("home/net/#", on_net_msg)
mqtt.subscribe("home/pressure", on_pressure_msg)
#mqtt.subscribe("home/gas", on_gas_msg)
mqtt.subscribe("home/dust", on_dust_msg)
mqtt.subscribe("home/node/#", on_home_msg)

mqtt.start()

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        log("irq")
        break
    except Exception, ex:
        traceback.print_stack(sys.stdout)
        raise

mqtt.stop()
mqtt.join()

# FIN
