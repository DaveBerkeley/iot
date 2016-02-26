
from system.jeenet import JeeNodeDev, message_info

#
#

class VoltageDev(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)

    def to_info(self, data):
        rx_fields = [ 
            (1<<1, "temp", "<h"),
            (1<<2, "voltage", "<H"), 
            (1<<3, "vcc", "<H"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0
        if not info.get("voltage") is None:
            info["voltage"] /= 1000.0
        if not info.get("vcc") is None:
            info["vcc"] /= 1000.0

        return info

    def get_poll_period(self):
        return None

# FIN
