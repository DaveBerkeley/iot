
from broker.jeenet import JeeNodeDev, message_info

#
#

class RelayDev(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)

    def to_info(self, data):
        rx_fields = [ 
            (1<<1, "temp", "<H"),
            (1<<2, "relay", "<B"), 
            (1<<3, "vcc", "<H"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0
        if not info.get("vcc") is None:
            info["vcc"] /= 1000.0

        return info

    def set_relay(self, state):
        assert state in [ 0, 1, ]
        fields = [ (1<<2, "<B", state), ]
        msg_id, raw = self.make_raw(self.ack_flag, fields)
        self.tx_message(msg_id, raw, "set_state", True)

    def get_poll_period(self):
        return 60

    api = JeeNodeDev.api + [ "set_relay" ]

# FIN
