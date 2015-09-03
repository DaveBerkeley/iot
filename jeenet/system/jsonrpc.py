#
#

from core import Device, log, get_device

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

class JsonRpcServer(Device):

    def __init__(self, *args, **kwargs):
        Device.__init__(self, *args, **kwargs)
        self.port = kwargs["port"]
        self.server = SimpleJSONRPCServer(('', self.port))
        self.server.register_function(self.push)
        self.server.register_function(self.call_device)

    def push(self, node, info):
        self.report(info, node)

    def call_device(self, name, fn_name, *args, **kwargs):
        log(name, fn_name, args, kwargs)

        info = { 
            "call" : name, 
            "fn" : fn_name,
            "args" : args, 
            "kwargs" : kwargs,
        }
        # call the device locally
        dev = get_device(name)
        log("found device", dev)
        if not fn_name in dev.api:
            raise Exception("no function '%s'" % fn_name)
        fn = getattr(dev, fn_name)
        return fn(*args, **kwargs)

    def run(self):
        log("json server ...")
        self.server.serve_forever()

    def kill(self):
        self.server.shutdown()

# FIN
