#!/usr/bin/python

import threading

import mosquitto

class Broker:

    def __init__(self, client_id=None, server = "mosquitto"):
        self.server = server
        self.client_id = client_id
        self.dead = False
        self.thread = None
        assert(client_id)
        self.client = mosquitto.Mosquitto(client_id)
        self.client.connect(self.server)

        def on_message(x):
            print "got", str(x)

        self.client.on_message = on_message

    def start(self):
        assert(self.thread is None)
        def run():
            while not self.dead:
                self.client.loop()

        self.thread = threading.Thread(target=run)
        self.thread.start()

    def join(self):
        self.client.disconnect()
        self.dead = True
        self.thread.join()

    def send(self, topic, data):
        self.client.publish(topic, data)

#
#

if __name__ == "__main__":
    broker = Broker("any_id_here")
    broker.send("home/pir", "{'pir':'1'}")

# FIN
