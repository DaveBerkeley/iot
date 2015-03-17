#
#

import time
import httplib
import urllib

from core import Reader, log, get_device

class IoT(Reader):

    def __init__(self, *args, **kwargs):
        self.broker = kwargs["broker"]
        self.server = kwargs["server"]
        self.verbose = kwargs.get("verbose", False)
        Reader.__init__(self, *args, **kwargs)

    def forward(self, dev):
        def send():
            def tx(node, data):
                self.report(node, data)
            return tx

        self.broker.register(dev, send())

    def report(self, node, data):
        log("Iot", node, data)
        d = {}
        for key, value in data.items():
            if key == "mid":
                continue
            d[key] = value

        args = []
        d["subtopic"] = "jeenet/" + node
        for key, value in d.items():
            args.append("%s=%s" % (key, value))
        get = "/wiki/iot.cgp?" + "&".join(args)
        http = httplib.HTTPConnection(self.server)
        http.request("GET", get)
        r = http.getresponse()

    def get(self):
        log("Iot get")
        return None, None

# FIN
