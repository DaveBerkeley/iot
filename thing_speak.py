#!/usr/bin/python

import urllib
import httplib

"""
api_key (string) - Write API key for this specific channel (required). The Write API key can optionally be sent via a THINGSPEAKAPIKEY HTTP header.
field1 (string) - Field 1 data (optional)
field2 (string) - Field 2 data (optional)
field3 (string) - Field 3 data (optional)
field4 (string) - Field 4 data (optional)
field5 (string) - Field 5 data (optional)
field6 (string) - Field 6 data (optional)
field7 (string) - Field 7 data (optional)
field8 (string) - Field 8 data (optional)
lat (decimal) - Latitude in degrees (optional)
long (decimal) - Longitude in degrees (optional)
elevation (integer) - Elevation in meters (optional)
status (string) - Status update message (optional)
twitter (string) - Twitter username linked to ThingTweet (optional)
tweet (string) - Twitter status update (optional)
created_at (datetime
"""

class ThingSpeak:

    url = "api.thingspeak.com"

    def post(self, key, **kwargs):
        d = {
            "key" : key,
        }

        d.update(kwargs)

        params = urllib.urlencode(d)
        headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
        conn = httplib.HTTPSConnection(self.url)
        #print d

        try:
            conn.request("POST", "/update", params, headers)
            response = conn.getresponse()
            #print response.status, response.reason
            data = response.read()
            conn.close()
            if response.status != 200:
                print "Error", response.status, response.reason
        except:
            print "connection failed"

#
#

from thing_speak_keys import keys

if __name__ == "__main__":
    key = keys["solar"]["write"]
    thingspeak = ThingSpeak()
    thingspeak.post(key=key, field1=200, field2=20, field3=12341234)

# FIN
