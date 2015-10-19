
import struct 

from system.core import log
from system.jeenet import JeeNodeDev, message_info

#
#

# Flash Commands
FLASH_INFO_REQ = 1
FLASH_INFO = 2
FLASH_CLEAR = 3
FLASH_CLEARED = 4
FLASH_WRITE = 5
FLASH_WRITTEN = 6
FLASH_CRC_REQ = 7
FLASH_CRC = 8
FLASH_READ_REQ = 9
FLASH_READ = 10
FLASH_REBOOT = 11

#
#

class FlashInterface:

    def __init__(self, *args, **kwargs):
        self.api = RelayDev.api + self.flash_api

    # Individual FLASH command handlers (radio->host)

    def cmd_info(self, info, data):
        blocks, size = struct.unpack("<HH", data)
        info["flash"] = { "cmd" : "info", "blocks" : blocks, "size" : size }
        return info

    def cmd_cleared(self, info, data):
        block, = struct.unpack("<H", data)
        info["flash"] = { "cmd" : "cleared", "block" : block }
        return info

    def cmd_crc(self, info, data):
        block, crc = struct.unpack("<HH", data)
        info["flash"] = { "cmd" : "crc", "block" : block, "crc" : crc }
        return info

    def cmd_written(self, info, data):
        addr, size = struct.unpack("<HH", data)
        info["flash"] = { "cmd" : "written", "addr" : addr, "size" : size }
        return info

    # high level data extractor.
    # called by JeeNodeDev when cracking message.
    def flash_to_info(self, data):
        hsize = struct.calcsize(self.fmt_header)
        hdr, payload = data[:hsize], data[hsize:]
        mid, dst, flags = struct.unpack(self.fmt_header, hdr)
        if not (flags & self.flash_flag):
            return None

        cmd, = struct.unpack("<B", payload[:1])
        log("flash_cmd", cmd)

        handlers = {
            # Add command handlers here
            FLASH_INFO      :   self.cmd_info,
            FLASH_CLEARED   :   self.cmd_cleared,
            FLASH_CRC       :   self.cmd_crc,
            FLASH_WRITTEN   :   self.cmd_written,
        }

        info = { "mid" : mid }

        def nowt(info, data):
            info["flash"] = "not implemented"
            return info

        fn = handlers.get(cmd, nowt)
        return fn(info, payload[1:])

    #   FLASH commands (host->radio)

    def flash_cmd(self, cmd, name, fields):
        log(name)
        f = [ (self.flash_flag, "<B", cmd), ]
        f += fields
        msg_id, raw = self.make_raw(self.ack_flag, f)
        self.tx_message(msg_id, raw, name, True)

    def flash_info_req(self):
        self.flash_cmd(FLASH_INFO_REQ, "flash_info_req", [])

    def flash_clear(self, block):
        fields = [ (0, "<H", block), ]
        self.flash_cmd(FLASH_CLEAR, "flash_clear", fields)

    def flash_crc_req(self, block):
        fields = [ (0, "<H", block), ]
        self.flash_cmd(FLASH_CRC_REQ, "flash_crc_req", fields)

    def flash_reboot(self):
        self.flash_cmd(FLASH_REBOOT, "flash_reboot", [])

    def flash_write(self, addr, data):
        fields = [ 
            (0, "<H", addr), 
            (0, "<H", len(data)),
            (0, "p", data),
        ]
        self.flash_cmd(FLASH_WRITE, "flash_write", fields)

    flash_api = [ 
        "flash_info_req",
        "flash_clear",
        "flash_crc_req",
        "flash_reboot",
        "flash_write",
    ]

#
#

class RelayDev(JeeNodeDev,FlashInterface):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)
        FlashInterface.__init__(self, *args, **kwargs)
        self.is_sleepy = True # not really

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
