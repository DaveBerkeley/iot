#!/usr/bin/python -u

import os
import time
import datetime
import json

import requests

# need a weather_conf.py with your key in ..
from weather_conf import KEY

# See OpenWeatherMap API http://openweathermap.org/
owm = "http://api.openweathermap.org/data/2.5/weather?id=%d&units=metric"

#
#

def fetch(ident, apikey=KEY):
    url = owm % ident
    if apikey:
        url += "&APPID=" + apikey
    r = requests.get(url)
    info = r.json()

    fields = {
        "main" : [ "temp", "pressure", "humidity" ],
        "wind" : [ "speed", "deg" ],
        "clouds" : [ "all" ],
        "rain" : [ "3h" ],
    }
    
    data = {}
    for section, names in fields.items():
        for field in names:
            if info.has_key(section):
                if info[section].has_key(field):
                    if data.get(section) is None:
                        data[section] = {}
                    data[section][field] = info[section][field]
    
    return data

#
#

f = None

def log_site(ident, name):
    try:
        info = fetch(ident)
    except Exception, ex:
        print str(ex)
        raise
    
    info["id"] = name
    info["src"] = "owm"

    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d.log")
    path = os.path.join(base, ymd)

    global f
    if f and (f.name != path):
        f = None

    dirname, x = os.path.split(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        f = None
        last_sector = None

    if f is None:
        f = file(path, "a")

    info["time"] = now.strftime("%Y/%m/%d %H:%M:%S")
    j = json.dumps(info) + "\n"
    f.write(j)
    f.flush()

#
#

base = "/usr/local/data/weather"

ids = {
    "Plymouth" : 3333181,
}

while True:
    for name, ident in ids.items():
        try:
            log_site(ident, name)
        except Exception, ex:
            print str(ex)
    time.sleep(60)

# FIN
