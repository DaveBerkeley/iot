#!/usr/bin/python

import time
import os
import json

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

#
#

class Handler:

    def handle(self, path):
        print path

    def dispatch(self, event):
        if event.event_type == "modified":
            path = event.src_path
            if path.endswith(".log"):
                self.handle(path)

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
