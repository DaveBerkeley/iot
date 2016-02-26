
from system.jeenet import JeeNodeDev, message_info

#
#

class PulseDev(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)
        self.is_sleepy = True

    def to_info(self, data):
        rx_fields = [ 
            (1<<0, "pulse", "<L"), 
            (1<<1, "vcc", "<H"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("vcc") is None:
            info["vcc"] /= 1000.0

        return info

    def get_poll_period(self):
        return None

# FIN
