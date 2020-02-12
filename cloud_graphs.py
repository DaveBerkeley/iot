#!/usr/bin/python -u

import time
import datetime
import traceback
import json
import sys
import os
from threading import Lock, Thread

import broker

from influxdb import InfluxDBClient

#sys.path.append("../keys")
#from thing_speak import ThingSpeak, keys

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
        try:
            fn(key, **kwargs)
        except Exception as ex:
            log("execute", "exception", str(ex))
    thread = Thread(target=run)
    thread.start()

#
#   InfluxDb database interface

class BaseDb:

    def make(self, measurement, value, secs, **kwargs):
        tags = {}
        try:
            value = float(value)
        except ValueError:
            pass
        ds = {
            'measurement' : measurement,
            'tags' : tags,
            'time' : int(secs * 1000000000),
            'fields' : { 'value' : value, },
        }

        for k, v in kwargs.items():
            tags[k] = v

        return ds

#
#

class DB(BaseDb):

    def __init__(self, name='iot'):
        self.db = InfluxDBClient(host='localhost', port=8086)
        self.db.switch_database(name)

    def send(self, points):
        print(points)
        self.db.write_points(points)

    def write(self, key, **kwargs):
        ds = []
        for k, v in kwargs.items():
            d = {
                'measurement' : k,
                'tags' : { 'src' : key },
                'fields' : { k : float(v), },
            }
            ds.append(d)
        #print ds
        self.db.write_points(ds)

#
#

def post(key, **kwargs):
    #log("post", key, kwargs)
    cloud.write(key, **kwargs)

#
#

def get_period(tag):
    # no rate limiting
    return datetime.timedelta(seconds=1)
    #t = {
    #    'dust' : 60*60,
    #    'gateway' : 30*60,
    #}
    #return datetime.timedelta(seconds=t.get(tag, 600))

# timestamps of last tx by tag
tags = {}
last = {}

def tx_cloud(tag, **kwargs):
    # check if it has changed
    state = last.get(tag)
    #if kwargs == state:
    #    log("No change", tag, kwargs)
    #    return

    # check the elapsed time since last post
    now = datetime.datetime.now()
    #again = tags.get(tag)
    #if not again is None:
    #    if again > now:
    #        log("Drop", tag, again - now, kwargs)
    #        return

    #key = keys[tag]["write"]
    key = tag
    log("TX", tag, kwargs)
    tags[tag] = now + get_period(tag)
    last[tag] = kwargs
    #return 
    try:
        #log("post", key, kwargs)
        execute(post, key, **kwargs)
    except Exception, ex:
        #traceback.print_stack(sys.stdout)
        log(str(ex))

#
#

topics = {
    "gateway" : [ "temp", ],
    "humiditydev_2" : [ "vcc", "humidity", "temp" ],
    "humiditydev_11" : [ "vcc", "humidity", "temp" ],
    "voltagedev_9" : [ "vcc", "temp", "voltage" ],
    "magnetometerdev_12" : [ "x", "y", "z", "vcc" ],
    "relaydev_7" : [ "vcc", "temp" ],
}

def on_jeenet_msg(x):
    data = json.loads(x.payload)

    topic = x.topic.split("/")[-1]

    fields = topics.get(topic)
    if not fields:
        log("No fields for", topic)
        log(topic, fields, data)
        return

    d = {}
    for i, field in enumerate(fields):
        value = data.get(field)
        if not value is None:
            d[field] = value

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
        d[field] = float(value)

        def delta(field, value, idx):
            last = last_net.get(field)
            if not last is None:
                d[field] = int(float(value)) - int(float(last))

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
    tx_cloud("barometer", pressure=pressure, sea=sea)

#
#

def on_humidity(x):
    data = json.loads(x.payload)
    temp = data['temp']
    humidity = data['humidity']
    dev = data['dev']
    tag = "humidity_" + str(dev)
    #log(tag, humidity, temp)
    tx_cloud(tag, humidity=humidity, temp=temp)

#
#

def on_water(x):
    data = json.loads(x.payload)
    changes = data['changes']
    today = data['today']
    dev = data['dev']
    tag = "water_" + str(dev)
    #log(tag, humidity, temp)
    tx_cloud(tag, water=changes, water_today=today)

#
#

def on_weather(x):
    data = json.loads(x.payload)
    main = data.get('main')
    if main is None:
        return

    temp = str(main['temp'])
    pressure = str(main['pressure'])
    humidity = str(main['humidity'])

    wind = data['wind']
    speed = str(wind['speed'])
    deg = str(wind['deg'])

    clouds = data['clouds']
    cover = str(clouds['all'])

    rain = data.get('rain')
    if rain:
        rain = str(rain['3h'])
    else:
        rain = "0"

    # typically 'owm.plymouth'
    tag = data.get('src', 'xx') + '.' + data.get('id','yy').lower()
    #log(tag, temp, pressure, humidity, speed, deg, cover, rain)
    tx_cloud(tag, temp=temp, sea=pressure, humidity=humidity, windspeed=speed, winddeg=deg, cloudall=cover, rain=rain)

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

node_lut = {
    # This is crap. The ipaddr (x.x.x.node) can change
    # Needs to be fixed to MAC address, and macaddr passed in.
    # These values checked 20-Feb-2019
    u'209' : 'snoopie_04', # front room
    u'165' : 'snoopie_05', # office
    u'231' : 'snoopie_08', # back room -over rad
    u'229' : 'snoopie_09', # bedroom
    u'104' : 'snoopie_04', # front room
    u'105' : 'snoopie_05', # office
    u'108' : 'snoopie_08', # back room -over rad
    u'109' : 'snoopie_09', # bedroom
}

def on_home_msg(x):
    data = json.loads(x.payload)
    # TODO : make this smarter!
    node = data.get("node")
    tag = node_lut.get(node)
    if tag is None:
        return

    d = {}
    for field in [ "temp", "pir" ]:
        value = data.get(field)
        if not value is None:
            d[field] = value
    if d:
        tx_cloud(tag, **d)

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
    tx_cloud("dust", dust=dust, dust5=dust_5, dust10=dust_10)

#
#

def on_rivers(x):
    data = json.loads(x.payload)
    level = data['level']
    # get date/time
    tt = data['time']
    fmt = "%Y/%m/%d %H:%M:%S"
    dt = datetime.datetime.strptime(tt, fmt)
    # extract epoch seconds
    epoch = datetime.datetime(1970, 1, 1)
    secs = (dt - epoch).total_seconds()

    # 
    d = { 
        'river.site' : data['name'],
        'river.code' : data['id'],
    }
    point = cloud.make("river", level, secs, **d)
    cloud.send([ point ])

#
#   Solar Power

def on_solar(x):
    data = json.loads(x.payload)
    #log("SOLAR", data)

    kwh = data.get("power")
    #t = data.get("time")
    power = data.get("W")
    acc = data.get("today")

    tx_cloud("solar", power=power, kwh=kwh, total=acc)

#
#   Sump Pump monitor

def on_sump(x):
    data = json.loads(x.payload)
    #log("SUMP", data)

    distance = data.get("distance")
    #t = data.get("time")
    temp = data.get("temp")
    humidity = data.get("humidity")

    tx_cloud("sump", distance=distance, temp=temp, humidity=humidity)

#
#

def test(name):

    class Dummy(BaseDb):
        def write(self, key, **kwargs):
            log("put", key, kwargs)
        def send(self, *args):
            log("send", args)

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
        cloud = DB()

    mqtt = broker.Broker("thingspeak_" + str(os.getpid()), server="mosquitto")

    def wrap(fn):
        def f(line):
            try:
                fn(line)
            except Exception as ex:
                log("Exception", str(fn), str(ex))
        return f

    if 1:
        mqtt.subscribe("home/jeenet/#", wrap(on_jeenet_msg))
        mqtt.subscribe("home/net/#", wrap(on_net_msg))
        mqtt.subscribe("home/pressure", wrap(on_pressure_msg))
        mqtt.subscribe("home/dust", wrap(on_dust_msg))
        mqtt.subscribe("home/node/#", wrap(on_home_msg))
        mqtt.subscribe("home/solar", wrap(on_solar))
        mqtt.subscribe("home/humidity/#", wrap(on_humidity))
        mqtt.subscribe("home/weather", wrap(on_weather))
        mqtt.subscribe("home/water/#", wrap(on_water))
        mqtt.subscribe("rivers/level", wrap(on_rivers))
        mqtt.subscribe("home/underfloor/#", wrap(on_sump))

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
