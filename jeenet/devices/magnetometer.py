
from system.jeenet import JeeNodeDev, message_info

#
#

class MagnetometerDev(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)

    def to_info(self, data):
        rx_fields = [ 
            (1<<1, "temp", "<H"),
            (1<<2, "vcc", "<H"),
            (1<<3, "x", "<h"),
            (1<<4, "y", "<h"),
            (1<<5, "z", "<h"),
            (1<<6, "gain", "<B"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0
        if not info.get("vcc") is None:
            info["vcc"] /= 1000.0

        return info

    def get_poll_period(self):
        return None

# FIN
