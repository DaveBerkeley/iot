
from broker.jeenet import JeeNodeDev, message_info

#
#

class PirSensor(JeeNodeDev):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)

    def to_info(self, data):
        rx_fields = [ 
            (1<<0, "pir", "<B"), 
            (1<<1, "temp", "<H"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0

        # ack is now handled by the radio board
        #if flags & self.ack_flag:
        #    self.hello(0, msg_id=msg_id)
        return info

    def set_mode(self, mode):
        assert mode in [ 0, 1, 2 ]
        log("set mode", mode)
        fields = [ (1<<0, "<B", mode), ]
        msg_id, raw = self.make_raw(self.ack_flag, fields)
        self.tx_message(msg_id, raw, "set_mode", True)

    def get_poll_period(self):
        return None

    api = JeeNodeDev.api + [ "set_mode" ]

# FIN