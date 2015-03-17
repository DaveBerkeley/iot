
import struct
import time
import serial
from threading import Event

from core import Reader, Device, log, Message
import bencode

#
#   Message decode

def decode_message(data, header, fields):
    length = struct.calcsize(header)
    msg_id, node, present = struct.unpack(header, data[:length])
    data = data[length:]

    flags = present & 0xC000
    present &= 0x3FFF

    result = []
    for mask, name, field in fields:
        if mask & present:
            # not sure why 'p' format doesn't work in struct
            if field == "p":
                length = ord(data[0])
                d, = struct.unpack("%ds" % length, data[1:length+1])
                length += 1
            else:
                length = struct.calcsize(field)
                d, = struct.unpack(field, data[:length])
            data = data[length:]
            result.append(d)
        else:
            result.append(None)

    if len(data):
        log("Error: not all fields read", `data`)

    return msg_id, flags, result

def message_info(data, header, fields):
    msg_id, flags, data = decode_message(data, header, fields)
    info = { "mid" : msg_id }

    for (mask, name, fmt), value in zip(*[ fields, data ]):
        if not value is None:
            info[name] = value

    #log("mi:", flags, info)
    return msg_id, flags, info

#
#

class JeeNet(Reader):

    def __init__(self, *args, **kwargs):
        self.dev = kwargs.get("dev")
        self.baud = kwargs.get("baud", 57600)
        self.verbose = kwargs.get("verbose", False)
        self.s = None
        Reader.__init__(self, *args, **kwargs)
        self.parser = bencode.Parser(self.read)

    def reset(self):
        self.s.setRTS(1)
        time.sleep(1)
        self.s.setRTS(0)

        # flush any lurking input
        while self.s.read():
            pass

        if self.verbose:
            log("reset", self.dev)

    def read(self):
        while not self.killed:
            c = self.s.read(1)
            if len(c):
                return c

    def open(self):
        self.s = serial.Serial(self.dev, self.baud, timeout=1)

    def tx(self, node, data):
        if self.verbose:
            log('send', node, `data`)
        # TODO : put a lock on this resource
        self.s.write(bencode.encode([ node, data ]))

    def get(self):
        node, raw = self.parser.get()
        if self.verbose:
            log("jeenet", node, `raw`)
        assert type(raw) == type("123")
        return node, raw

#
#

devices = {}

class JeeNodeDev(Device):

    # msg_id, node, flags, present, reserved, data...
    fmt_header = "<BBH"
    ack_flag   = 0x8000
    admin_flag = 0x4000
    text_flag  = 0x2000

    def __init__(self, *args, **kwargs):
        Device.__init__(self, *args, **kwargs)
        if self.network:
            self.network.register(self.dev_id, self.on_net)
        if self.broker:
            self.broker.register("tick", self.on_clock)
        devices[self.dev_id] = self

    def on_net(self, node, data):
        assert node == self.dev_id
        info = self.to_info(data)
        #log("J on_net", node, info)
        # tell the broker
        self.report(info)    
        # let the device know the message has been rxd
        msg_id = info["mid"]
        self.on_message(msg_id)
        self.last_response = time.time()
        self.set_state("up", "node up", "message received")

    def on_timeout(self, msg):
        self.set_state("down", "node down", "timeout error")
 
    def on_clock(self, node, info):
        # called in broker thread on regular clock event
        now = info["time"]
        self.poll_messages(now)

    def to_info(self, data):
        raise Exception("Implement to_info()  in derived class")

    def make_msg(self, name, msg_id, raw):
        timeout = 1
        retries = 5
        msg = Message(name, msg_id, raw, None, retries, self.on_timeout, timeout)
        return msg

    def make_raw(self, flags, fields, msg_id=None):
        # fields as [ (bit_mask, fmt, value), ... ] in binary order

        mid = msg_id or self.get_msg_id()
        mask = flags
        args = ""
        for bit, fmt, value in fields:
            if bit:
                args += struct.pack(fmt, value)
            mask |= bit

        raw = struct.pack(self.fmt_header, mid, self.dev_id, mask)
        return mid, raw + args

    def hello(self, flags, msg_id=None):
        mid, raw = self.make_raw(flags, [], msg_id)
        if flags & self.ack_flag:
            msg = self.make_msg("hello", mid, raw)
            self.add_message(msg)
        self.tx(raw)

    def get_poll_period(self):
        # default poll period
        return 60.0

    api = Device.api + [ "hello" ]

#
#   Gateway

class Gateway(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)

    def to_info(self, data):
        fields = [ (1<<0, "temp", "<H") ]
        msg_id, flags, info = message_info(data, self.fmt_header, fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0

        if flags & self.ack_flag:
            self.hello(0, msg_id=msg_id)
        return info

    def get_poll_period(self):
        return 10.0

#
#

class Monitor(Device):

    def __init__(self, *args, **kwargs):
        Device.__init__(self, *args, **kwargs)
        self.period = kwargs["period"]
        self.dead_time = kwargs["dead_time"]
        self.event = Event()
        self.waits = []

    def poll_device(self, device):
        if not hasattr(device, "hello"):
            return
        log("hello", device.node)
        device.hello(device.ack_flag)

    def make_waits(self):
        waits = []
        now = time.time()
        for node, device in devices.items():
            period = device.get_poll_period()
            if period:
                next_time = now + period
                waits.append([ next_time, period, device ])
        return waits

    def run(self):
        waits = self.make_waits()

        while not self.killed:

            if len(self.make_waits()) != len(waits):
                raise Exception("doesn't handle added items yet")

            waits.sort()
            top = waits[0]

            next_time, period, device = top
            diff = next_time - time.time()
            if diff > 0.0:
                self.event.wait(diff)
                continue

            self.poll_device(device)
            # increment next poll time
            top[0] += top[1]
            # don't trash the airwaves with a block of hellos
            # or it will stomp on any acks
            time.sleep(0.01)

    def kill(self):
        Device.kill(self)
        self.event.set()

# FIN
