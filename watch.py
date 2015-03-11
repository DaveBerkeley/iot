#!/usr/bin/python

import time
import os
import json

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

#
#

class Handler:

    def __init__(self):
        self.f = None
        self.path = None

    def on_data(self, data):
        print data

    def handle_file_change(self, path):
        if self.path != path:
            self.f = None
        if self.f is None:
            self.f = open(path, "r")
            self.path = path

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
