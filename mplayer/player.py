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

#
#

p = "/usr/local/data/music/Misc/venus.mp3"

class Player:

    def __init__(self):
        self.status = "stop"
        self.posn = 0
        self.length = 0
        self.p = mplayer.Player()

    def on_mqtt(self, x):
        data = json.loads(x.payload)
        print data
        if data == "stop":
            self.p.stop()
            self.status = data
            self.posn = 0
        elif data == "play":
            self.play(p)
            self.status = data
        elif data == "pause":
            if self.status == "play":
                self.posn = self.p.time_pos
                self.length = self.p.length
                self.p.stop()
                self.status = "pause"
            else:
                self.play(p)
                self.p.time_pos = self.posn
                self.status = "play"

        elif data == "dir":
            print dir(self.p)

    def get_status(self):
        if self.p.length:
            pc = 100.0 * self.p.time_pos / self.p.length
        else:
            if self.status == "pause":
                pc = 100 * self.posn / self.length
            else:
                pc = 0
        d = { 
            "status" : self.status,
            "pos" : self.p.time_pos or self.posn,
            "length" : self.p.length,
            "speed" : self.p.speed,
            "percent" : int(pc),
        }
        return json.dumps(d)

    def play(self, path):
        self.p.loadfile(path)

#
#

player = Player()

mqtt = broker.Broker("player", server="mosquitto")
mqtt.subscribe("home/player/control", player.on_mqtt)

mqtt.start()

#player.play(p)

topic = "home/player/status"

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
