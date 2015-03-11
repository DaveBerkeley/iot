#!/usr/bin/python

import time

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

#
#

class Handler:
    def dispatch(self, event):
        print event

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
