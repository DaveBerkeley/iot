#!/usr/bin/python -u

import time
import datetime
import json
import httplib
import socket
import traceback
import sys
from threading import Lock

import broker

from xively_conf import key, feed

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

#
#

class CosmWriter:

    host = 'api.cosm.com'
    agent = "python cosm 1.0"
 
    def __init__(self, feed, key, https=True):
        self.headers = {
            "Content-Type"  : "application/x-www-form-urlencoded",
            "X-ApiKey"      : key,
            "User-Agent"    : self.agent,
        }
        self.params = "/v2/feeds/" + str(feed)
        if https:
            self.Connection = httplib.HTTPSConnection
        else:
            self.Connection = httplib.HTTPConnection

    def put(self, info):
        items = []

        for key, value in info:
            items.append( { "id" : key, "current_value" : value } )

        data = {
          "version" : "1.0.0",
          "datastreams": items,
        }
        body = json.dumps(data)

        http = self.Connection(self.host)
        http.request("PUT", self.params, body, self.headers)
        response = http.getresponse()
        http.close()
        return response.status, response.reason

#
#

last_send = {}

def tx_info(name, info):
    now = time.time()
    last_sent = last_send.get(name)
    if last_sent != None:
        if (last_sent + 60) > now:
            return

    log("COSM PUT", name, info)
    try:
        cosm.put(info)
        last_send[name] = now
    except Exception, ex:
        traceback.print_stack(sys.stdout)
        log(str(ex))

#
#

def on_jeenet_msg(x):
    data = json.loads(x.payload)
    #log(data)

    if data.get("temp") is None:
        return

    topic = x.topic.split("/")[-1]
    fields = [ "vcc", "temp", "voltage", "humidity" ]

    info = []

    for field in fields:
        d = data.get(field)
        if not d is None:
            name = topic + "_" + field
            info.append((name, d))

    tx_info(topic, info)

def on_net_msg(x):
    data = json.loads(x.payload)

    info = []
    if data.get("host") == "klatu":
        t0 = data.get("temp_0")
        t1 = data.get("temp_1")
        if (t0 is None) or (t1 is None):
            return
        info.append(( str("klatu_0"), t0 ))
        info.append(( str("klatu_1"), t1 ))
        tx_info("klatu_temp", info)

def on_pressure_msg(x):
    data = json.loads(x.payload)
    info = ( 
        ( "pressure", data["p"], ), 
        ( "sea", data["sea"], ), 
    )
    tx_info("pressure", info)

def on_home_msg(x):
    data = json.loads(x.payload)
    # TODO : make this smarter!
    ip = data.get("ipaddr")
    # get the final octet of the ip address
    raw = socket.inet_aton(ip)
    end = ord(raw[3])
    # move eg. 192.168.0.105 to 05
    if end > 100:
        end -= 100

    if data.get("temp"):
        field = "pir_%02d" % end
        info = ( 
            ( field, data["temp"], ), 
        )
        tx_info("home", info)

def on_gas_msg(x):
    data = json.loads(x.payload)
    info = ( 
        ( "gas_m3", 1000 * float(data["m3"]), ), 
        ( "gas_sector", data["sector"], ), 
        ( "gas_rate", 1000000 * float(data["rate"]), ), 
        ( "gas_rot", float(data["rots"]), ), 
    )
    tx_info("gas", info)

def on_dust_msg(x):
    data = json.loads(x.payload)
    info = ( 
        ( "dust", data["dust"], ), 
        ( "dust_5", data["dust_5"], ), 
        ( "dust_10", data["dust_10"], ), 
    )
    tx_info("dust", info)

#
#

cosm = CosmWriter(feed, key)

mqtt = broker.Broker("xively", server="mosquitto")
mqtt.subscribe("home/jeenet/#", on_jeenet_msg)
mqtt.subscribe("home/net/#", on_net_msg)
mqtt.subscribe("home/pressure", on_pressure_msg)
mqtt.subscribe("home/gas", on_gas_msg)
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
