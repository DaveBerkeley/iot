#!/usr/bin/python -u

import time
import datetime
import traceback
import json
import sys
import os
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

def tx_cloud(tag, **kwargs):
    key = keys[tag]["write"]
    log("TX", tag, kwargs)
    try:
        execute(cloud.post, key, **kwargs)
    except Exception, ex:
        #traceback.print_stack(sys.stdout)
        log(str(ex))

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
    global last_net
    data = json.loads(x.payload)

    fields = [ 'temp_0', 'temp_1', 'load_0', 'load_1', 'rx', 'tx', 'drx', 'dtx' ]

    host = data.get("host")
    if not host:
        return

    d = {}
    for i, field in enumerate(fields):
        value = data.get(field)
        if value is None:
            continue
        name = "field" + str(i+1)
        d[name] = float(value)

        def delta(field, value, idx):
            last = last_net.get(field)
            if not last is None:
                name = "field" + str(idx+1)
                d[name] = int(value) - int(last)

        delta("rx", data.get("rx"), fields.index("rx")+2)
        delta("tx", data.get("tx"), fields.index("tx")+2)

    last_net = data
    tx_cloud(host, **d)

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

#
#   Moving Average Filter

class Filter:

    def __init__(self, ntaps):
        self.ntaps = ntaps
        self.data = None

    def filter(self, data):
        if self.data is None:
            self.data = [ data, ] * self.ntaps
        self.data = self.data[1:] + [ data ]
        return int(sum(self.data) / float(self.ntaps))

lpf = Filter(3)

solar_last_w = None
solar_last_t = None
solar_yesterday = None
solar_yesterday_w = None

def on_solar(x):
    global solar_last_w, solar_last_t, solar_yesterday, solar_yesterday_w
    data = json.loads(x.payload)
    #log("SOLAR", data)

    kwh = data.get("power")
    t = data.get("time")

    t = datetime.datetime.strptime(t, "%Y/%m/%d %H:%M:%S")

    if solar_last_w is None:
        solar_last_w = kwh
        solar_last_t = t

        if solar_yesterday_w is None:
            solar_yesterday_w = kwh
        return

    today = t.date()
    if today != solar_last_t.date():
        # day change
        solar_yesterday = solar_last_t
        solar_yesterday_w = solar_last_w

    def get_power(p1, p2, t1, t2):
        dt = t1 - t2
        dt = dt.total_seconds() / 3600.0

        if not dt:
            return None

        dw = p1 - p2
        power = dw / dt
        return power

    power = get_power(kwh, solar_last_w, t, solar_last_t)
    solar_last_t = t
    solar_last_w = kwh

    power = lpf.filter(power)

    if not solar_yesterday_w is None:
        acc = kwh - solar_yesterday_w
    else:
        acc = 0

    tx_cloud("solar", field1=power, field2=kwh, field3=acc)

#
#

def test(name):

    class Dummy:
        def post(self, key, **kwargs):
            log("put", key, kwargs)

    global cloud
    cloud = Dummy()

    if name != "broker":
        return

    paths = [
        "/usr/local/data/solar/2017/06/11.log",
        "/usr/local/data/solar/2017/06/12.log",
    ]

    class Data:
        def __init__(self, d):
            self.payload = d

    class xBroker:
        def __init__(self, name, **kwargs):
            self.idx = 0
        def open(self, path):
            self.f = open(path)
            parts = path.split("/")
            parts = parts[-3:]
            parts[-1] = parts[-1].split(".")[0]
            self.ymd = "/".join(parts)
        def subscribe(self, topic, fn):
            self.fn = fn
        def start(self):
            while True:
                if self.idx >= len(paths):
                    break
                self.open(paths[self.idx])
                self.idx += 1
                for line in self.f:
                    line = line.strip()
                    hms, kwh = line.split()
                    d = {
                        "time" : self.ymd + " " + hms,
                        "power" : int(kwh),
                    }
                    j = json.dumps(d)
                    self.fn(Data(j))
            sys.exit(0)

    class xbroker:
        Broker = xBroker

    global broker
    broker = xbroker

#
#

if __name__ == "__main__":

    if len(sys.argv) > 1:
        test(sys.argv[1])
    else:
        cloud = ThingSpeak()

    mqtt = broker.Broker("thingspeak_" + str(os.getpid()), server="mosquitto")
    mqtt.subscribe("home/jeenet/#", on_jeenet_msg)
    mqtt.subscribe("home/net/#", on_net_msg)
    mqtt.subscribe("home/pressure", on_pressure_msg)
    mqtt.subscribe("home/dust", on_dust_msg)
    mqtt.subscribe("home/node/#", on_home_msg)
    mqtt.subscribe("home/solar", on_solar)

    #mqtt.subscribe("home/gas", on_gas_msg)
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
