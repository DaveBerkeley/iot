
import math

from system.core import log
from system.jeenet import JeeNodeDev, message_info

#   Convert between power and phase
#

def to_phase(percent):
    return percent

def from_phase(phase):
    return phase

#   Triac device
#

class Triac(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)
        self.last_set_percent = 0

    def to_info(self, data):
        fields = [ 
            (1<<0, "power", "<H"), 
            (1<<1, "temp", "<H"), 
            (self.text_flag, "text", "p"),
        ]
        msg_id, flags, info = message_info(data, self.fmt_header, fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0

        if info.get("power"):
            info["power"] = from_phase(info["power"])

        # ack is now handled by the radio board
        #if flags & self.ack_flag:
        #    self.hello(0, msg_id=msg_id)
        return info

    def on_timeout(self, msg):
        JeeNodeDev.on_timeout(self, msg)
        self.last_set_percent = None

    def set_power(self, percent):
        assert 0 <= percent <= 100
        if self.last_set_percent == percent:
            return

        if self.state == "0":
            return

        power = to_phase(percent)
        log("set power", percent, "%, phase", power, "%")

        fields = [ (1<<0, "<H", power), ]
        msg_id, raw = self.make_raw(self.ack_flag, fields)
        self.tx_message(msg_id, raw, "set_power", True)
        self.last_set_percent = percent

    def on_up(self):
        self.set_power(self.last_set_percent)

    api = JeeNodeDev.api + [ "set_power" ]

# FIN
