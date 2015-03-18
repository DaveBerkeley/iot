#!/usr/bin/python -u

import time
import datetime
import json
import httplib
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

def get_name(topic):
    parts = topic.split("/")
    idxs = [ "pir_1", "triac_4", "gateway", ]
    for i, name in enumerate(idxs):
        if name == parts[-1]:
            return i, name
    return None, None

#
#

last_send = {}

def on_msg(x):
    data = json.loads(x.payload)
    #log(data)

    if data.get("temp") is None:
        return

    idx, name = get_name(x.topic)
    if name is None:
        return

    now = time.time()
    last_sent = last_send.get(name)
    if last_sent != None:
        if (last_sent + 60) > now:
            return

    info = ( ( str(idx), data["temp"], ), )
    log("COSM PUT", name, info)
    cosm.put(info)
    last_send[name] = now

#
#

cosm = CosmWriter(feed, key)

mqtt = broker.Broker("xively", server="mosquitto")
mqtt.subscribe("home/jeenet/#", on_msg)

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
