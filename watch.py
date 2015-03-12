#!/usr/bin/python

import time
import os
import json
import optparse

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

from broker import Broker

#
#

class Handler:

    def __init__(self, broker, seek):
        self.broker = broker
        self.f = None
        self.path = None
        self.seek = seek

    def on_data(self, data):
        print data
        if data.get("pir") != None:
            self.broker.send("home/pir", json.dumps(data))

    def handle_file_change(self, path):
        if self.path != path:
            self.f = None
        if self.f is None:
            self.f = open(path, "r")
            self.path = path
            if self.seek:
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

iot_dir = "/usr/local/data/iot"
rivers_dir = "/usr/local/data/share/dave/flood"

if __name__ == "__main__":

    p = optparse.OptionParser()
    p.add_option("-i", "--iot", dest="iot", default=iot_dir)
    p.add_option("-r", "--rivers", dest="rivers", default=rivers_dir)
    p.add_option("-s", "--seek", dest="seek", action="store_true")
    opts, args = p.parse_args()    

    paths = [
        opts.iot,
        opts.rivers,
    ]

    server = "mosquitto"
    print "connect to", server
    broker = Broker("watcher", server=server)
    broker.start()

    event_handler = Handler(broker, seek=opts.seek)

    observer = Observer()
    for path in paths:
        print "monitor", path
        observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        broker.stop()
        observer.stop()

    broker.join()
    observer.join()

# FIN
