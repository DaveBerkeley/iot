#!/usr/bin/python

import time
import os
import json

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

#
#

import socket
import threading

ADDR = "esp8266_1"
PORT = 5000

def relay():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto("on", (ADDR, PORT))

    def defer():
        time.sleep(2)
        sock.sendto("off", (ADDR, PORT))

    thread = threading.Thread(target=defer)
    thread.start()

#
#

class Handler:

    def __init__(self):
        self.f = None
        self.path = None

    def on_data(self, data):
        print data
        #if data.get("ipaddr") == "192.168.0.105":
        if data.get("pir") == "1":
            relay()

    def handle_file_change(self, path):
        if self.path != path:
            self.f = None
        if self.f is None:
            self.f = open(path, "r")
            self.path = path
            # TODO : remove me?
            # ignore the initial data ... TEMP
            self.f.seek(0, os.SEEK_END)

        # read all the pending changes
        while True:
            jdata = self.f.readline()
            if not jdata:
                break
            data = json.loads(jdata)
            self.on_data(data)

    def dispatch(self, event):
        if event.event_type == "modified":
            path = event.src_path
            if path.endswith(".log"):
                self.handle_file_change(path)

#
#

if __name__ == "__main__":

    path = "/usr/local/data/iot"

    event_handler = Handler()

    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

# FIN
