#!/usr/bin/python

import sys
import time
import datetime
import json

sys.path.append("..") # for broker

import broker

# https://github.com/baudm/mplayer.py
import mplayer

def log(*args):
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print

p = "/usr/local/data/music/Misc/venus.mp3"

topic = "home/player/status"

class Player:

    def __init__(self):
        self.status = "stop"
        self.p = mplayer.Player()

    def on_mqtt(self, x):
        data = json.loads(x.payload)
        print data

    def get_status(self):
        d = { 
            "status" : self.status,
        }
        return json.dumps(d)

    def play(self, path):
        self.p.loadfile(path)

player = Player()

mqtt = broker.Broker("player", server="mosquitto")
mqtt.subscribe("home/player/control", player.on_mqtt)

mqtt.start()

player.play(p)

while True:
    try:
        time.sleep(1)
        status = player.get_status()
        mqtt.send(topic, status)
    except KeyboardInterrupt:
        log("irq")
        break

mqtt.stop()
mqtt.join()

# FIN
