
import struct 
import base64

from core import log

#
#

# Flash Commands
FLASH_INFO_REQ = 1
FLASH_INFO = 2
#FLASH_CLEAR = 3
#FLASH_CLEARED = 4
FLASH_WRITE = 5
FLASH_WRITTEN = 6
FLASH_CRC_REQ = 7
FLASH_CRC = 8
FLASH_READ_REQ = 9
FLASH_READ = 10
FLASH_REBOOT = 11
FLASH_SET_FAST_POLL = 12

#
#

class FlashInterface:

    def __init__(self, *args, **kwargs):
        self.api = self.api + self.flash_api
        log("FlashInterface", args, kwargs)

    # Individual FLASH command handlers (radio->host)

    def cmd_info(self, info, data):
        blocks, size, packet_size = struct.unpack("<HHH", data)
        info["flash"] = { 
            "cmd" : "info", 
            "blocks" : blocks, 
            "size" : size,
            "packet" : packet_size,
        }
        return info

    def cmd_crc(self, info, data):
        addr, size, crc = struct.unpack("<LHH", data)
        info["flash"] = { "cmd" : "crc", "addr" : addr, "size" : size, "crc" : crc }
        return info

    def cmd_written(self, info, data):
        addr, size, crc = struct.unpack("<LHH", data)
        info["flash"] = { 
            "cmd" : "written", 
            "addr" : addr, 
            "size" : size,
            "crc" : crc,
        }
        return info

    def cmd_read(self, info, data):
        # TODO : fix variable length fields
        addr, size = struct.unpack("<LH", data)
        info["flash"] = { "cmd" : "read", "addr" : addr, "size" : size }
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
            FLASH_CRC       :   self.cmd_crc,
            FLASH_WRITTEN   :   self.cmd_written,
            FLASH_READ      :   self.cmd_read,
        }

        info = { "mid" : mid }

        def nowt(info, data):
            info["flash"] = "not implemented"
            return info

        fn = handlers.get(cmd, nowt)
        return fn(info, payload[1:])

    #   Send FLASH command to radio

    def flash_cmd(self, cmd, name, fields, payload=""):
        log(name)
        f = [ (self.flash_flag, "<B", cmd), ]
        f += fields
        msg_id, raw = self.make_raw(self.ack_flag, f)
        # JsonRpc will convert strings to unicode!
        # so turn them back into bytes.
        payload = bytes(payload)
        raw += payload
        #log("flash_cmd", [ str(x) for x in raw ])
        self.tx_message(msg_id, raw, name, True)

    #   FLASH commands (host->radio)

    def flash_info_req(self):
        log("flash_info_req", "xxxx")
        self.flash_cmd(FLASH_INFO_REQ, "flash_info_req", [])

    def flash_crc_req(self, addr, size):
        fields = [ 
            (self.flash_flag, "<L", addr), 
            (self.flash_flag, "<H", size), 
        ]
        self.flash_cmd(FLASH_CRC_REQ, "flash_crc_req", fields)

    def flash_reboot(self):
        self.flash_cmd(FLASH_REBOOT, "flash_reboot", [])

    def flash_write(self, addr, data, as64=False):
        if (as64):
            data = base64.b64decode(data)
        fields = [ 
            (self.flash_flag, "<L", addr), 
            (self.flash_flag, "<H", len(data)),
        ]
        self.flash_cmd(FLASH_WRITE, "flash_write", fields, data)

    def flash_read_req(self, addr, bytes):
        fields = [ 
            (self.flash_flag, "<L", addr), 
            (self.flash_flag, "<H", bytes),
        ]
        self.flash_cmd(FLASH_READ_REQ, "flash_read_req", fields)

    def flash_fast_poll(self, state):
        fields = [ 
            (self.flash_flag, "<B", state), 
        ]
        self.flash_cmd(FLASH_SET_FAST_POLL, "flash_fast_poll", fields)

    flash_api = [ 
        "flash_info_req",
        "flash_crc_req",
        "flash_reboot",
        "flash_write",
        "flash_read_req",
        "flash_fast_poll",
    ]

#   FIN
