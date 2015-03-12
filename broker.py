#!/usr/bin/python

import mosquitto

class Broker:

    def __init__(self, server = "mosquitto", client_id=None):
        self.server = server
        self.client_id = client_id
        self.client = mosquitto.Mosquitto(client_id)
        self.client.connect(self.server)

    def send(self, topic, data):
        self.client.publish(topic, data)

#
#

if __name__ == "__main__":
    broker = Broker(client_id="any_id_here")
    broker.send("home/pir", "{'pir':'1'}")

# FIN
