#!/usr/bin/python

import threading

# https://eclipse.org/paho/clients/python/docs/
import paho.mqtt.client as paho

#
#

class Broker:

    def __init__(self, client_id=None, server=None):
        self.server = server
        self.client_id = client_id
        self.dead = False
        self.thread = None
        self.subscribes = {}
        assert(client_id)
        self.client = paho.Client(client_id)
        self.client.connect(self.server)

        def on_message(client, x, msg):
            handler = self.subscribes.get(msg.topic)
            if handler:
                handler(msg)
                return
            handlers = []
            for name, handler in self.subscribes.items():
                if not name.endswith("#"):
                    continue
                idx = name.find("#")
                if name[:idx] == msg.topic[:idx]:
                    handlers.append(handler)

            if not handlers:
                print "no handler for", str(msg.topic), str(msg.payload)
            else:
                for handler in handlers:
                    handler(msg)

        self.client.on_message = on_message

    def start(self):
        assert(self.thread is None)
        def run():
            while not self.dead:
                self.client.loop()

        self.thread = threading.Thread(target=run)
        self.thread.start()

    def stop(self):
        self.client.disconnect()
        self.dead = True

    def join(self):
        self.thread.join()

    def send(self, topic, data):
        self.client.publish(topic, data)

    def subscribe(self, topic, callback):
        self.subscribes[topic] = callback
        self.client.subscribe(topic)

    def unsubscribe(self, topic):
        self.client.unsubscribe(topic)
        del self.subscribes[topic]

#
#

if __name__ == "__main__":
    broker = Broker("any_id_here", server="mosquitto")
    broker.send("home/pir", "{'pir':'1'}")

# FIN
