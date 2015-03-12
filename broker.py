#!/usr/bin/python

import mosquitto

class Broker:

    def __init__(self, client_id=None, server = "mosquitto"):
        self.server = server
        self.client_id = client_id
        assert(client_id)
        self.client = mosquitto.Mosquitto(client_id)
        self.client.connect(self.server)

    def send(self, topic, data):
        self.client.publish(topic, data)

#
#

if __name__ == "__main__":
    broker = Broker("any_id_here")
    broker.send("home/pir", "{'pir':'1'}")

# FIN
