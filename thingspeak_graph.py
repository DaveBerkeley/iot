#!/usr/bin/python

import httplib
import json

con = httplib.HTTPConnection("api.thingspeak.com")
con.request("GET", "/channels/390713/fields/2.json?days=1")
#con.request("GET", "/channels/390713/fields/2.json")

r1 = con.getresponse()
#print r1.status, r1.reason
j = r1.read()
print j
import sys
sys.exit(0)

data = json.loads(j)
#print data

for item in data["feeds"]:
    print item

# channel fields : description, field1, field1, ... latitude, longitude, id, name
#print data["channel"]

# FIN
