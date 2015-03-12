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

iot_dir = "/usr/local/data/iot"
rivers_dir = "/tmp/usr/local/data/rivers"

paths = [
    iot_dir,
    rivers_dir,
]

#
#

class Handler:

    def __init__(self, broker, seek):
        self.broker = broker
        self.files = {}
        for path in paths:
            self.files[path] = None
        self.seek = seek

    def on_data(self, tree, data):
        print str(data)
        #if data.get("pir") != None:
        self.broker.send("home/pir", data)

    def handle_file_change(self, path):
        tree = None
        for p in paths:
            if path.startswith(p):
                tree = p
                break
        print "found", tree

        f = self.files.get(tree)
        if not f is None:
            print str(f.name), str(path)
            if f.name != path:
                print "changed", path
                self.files[tree] = None
                f = None

        newfile = False
        if f is None:
            print "open", path
            newfile = True
            f = open(path, "r")
            self.files[tree] = f

        print f

        if newfile and self.seek:
            print "seek", f
            f.seek(0, os.SEEK_END)

        # read all the pending changes
        while True:
            data = f.readline()
            if not data:
                break
            self.on_data(tree, data)

    def dispatch(self, event):
        if event.event_type == "modified":
            path = event.src_path
            if path.endswith(".log"):
                self.handle_file_change(path)

#
#

if __name__ == "__main__":

    p = optparse.OptionParser()
    p.add_option("-s", "--seek", dest="seek", action="store_true")
    opts, args = p.parse_args()    

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
