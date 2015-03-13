#!/usr/bin/python

import threading

import mosquitto

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
        self.client = mosquitto.Mosquitto(client_id)
        self.client.connect(self.server)

        def on_message(x):
            handler = self.subscribes.get(x.topic)
            if handler is None:
                print "got", str(x)
            else:
                handler(x)

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
