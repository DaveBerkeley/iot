
import os
import time
import datetime
import struct
import httplib
import json
import traceback
from Queue import Queue
from threading import Thread, Lock

import serial

import bencode

#
#

log_lock = Lock()

verbose = True

def log(*args):
    if not verbose:
        return
    log_lock.acquire()
    now = datetime.datetime.now()
    ymd = now.strftime("%Y/%m/%d")
    hms = now.strftime("%H:%M:%S.%f")
    print ymd + " " + hms[:-3],
    for arg in args:
        print arg,
    print
    log_lock.release()

#
#

class Reader:

    def __init__(self, *args, **kwargs):
        self.handlers = {}
        self.killed = False

    # TODO : add thread lock to handler list

    def register(self, node, handler):
        if self.handlers.get(node):
            self.handlers[node].append(handler)
        else:
            self.handlers[node] = [ handler ]

    def run_handlers(self, match, node, data):
        handlers = self.handlers.get(match)
        if handlers:
            for handler in handlers:
                try:
                    handler(node, data)
                except Exception, ex:
                    log(`ex`, node, `data`, traceback.format_exc())

    def run(self):
        try:
            while not self.killed:
                node, data = self.get()
                if node is None:
                    break
                # node 0 is a special case that matches all messages
                for match in [ node, 0 ]:
                    self.run_handlers(match, node, data)
                if not self.handlers.get(node):
                    # node -1 is a special case for unhandled messages
                    self.run_handlers(-1, node, data)
        except KeyboardInterrupt:
            log(`self`, "keyirq")
        except Exception, ex:
            log(`ex`, traceback.format_exc())

    def kill(self):
        self.killed = True

#
#

class Broker(Reader):

    def __init__(self, verbose=False):
        Reader.__init__(self)
        self.queue = Queue()
        self.verbose = verbose

    def get(self):
        node, data = self.queue.get()
        if not node is None:
            assert type(data) == type({1:1})
        return node, data

    def send(self, node, data):
        if self.verbose:
            scope = data.get("scope")
            if scope != "internal":
                log("broker.send", node, `data`)
        self.queue.put((node, data))

    def kill(self):
        self.queue.put((None, None))

#
#

class Message:

    def __init__(self, name, msg_id, raw, on_ack, retries, on_timeout, timeout):
        self.name = name
        self.msg_id = msg_id
        self.msg = raw
        self.on_ack = on_ack
        self.retries = retries
        self.on_timeout = on_timeout
        self.timeout = timeout
        self.fail_time = time.time() + timeout
        self.deleted = False

#
#

devices = {}

on_new_handlers = []

def on_new_device(handler):
    on_new_handlers.append(handler)

not_an_id = 0
def noid():
    global not_an_id
    not_an_id -= 1
    return not_an_id

class Device:
 
    def __init__(self, node=None, network=None, broker=None, **kwargs):
        self.dev_id = kwargs.get("dev_id")
        node = node or noid()
        self.node = node
        self.network = network
        assert not devices.get(node)
        devices[node] = self
        self.broker = broker
        self.msg_id = 1
        # TODO : lock the messages
        self.messages = []
        self.last_response = None
        self.state = None
        self.killed = False
        self.is_sleepy = False

        # run any 'on new device' code
        for handler in on_new_handlers:
            handler(node, self)

    def tx(self, msg):
        self.network.tx(self.dev_id, msg)

    def report(self, info, node=None):
        self.broker.send(node or self.node, info)

    def set_state(self, state, error, why):
        was, self.state = self.state, state
        if was != state:
            self.report(
                {
                    "error" : error, 
                    "why" : why,
                    "last response" : self.last_response,
                } 
            )
            self.report_state()

    def report_state(self):
        self.report( { "state" : self.state })

    def get_msg_id(self):
        i = self.msg_id
        self.msg_id = (self.msg_id + 1) % 256
        if not self.msg_id:
            self.msg_id = 1
        return i

    def add_message(self, msg):
        # TODO : add lock
        #self.messages.append(msg)
        pass # TODO : revisit the whole polling scheme

    def clear_messages(self, *args, **kwargs):
        # TODO : add lock
        if not kwargs:
            self.messages = []
            return

        for i, msg in enumerate(self.messages):
            for field, value in kwargs.items():
                attr = getattr(msg, field)
                if attr:
                    if attr == value:
                        msg.deleted = True

    def tx_message(self, msg_id, raw, msg_name, replace):
        #log("tx_message", msg_id, self)
        msg = self.make_msg(msg_name, msg_id, raw)
        if replace:
            self.clear_messages(name=msg_name)
        if not self.is_sleepy:
            self.add_message(msg)
        self.tx(raw)

    def poll_messages(self, now):
        # TODO : add lock
        for i, message in enumerate(self.messages):
            if message.deleted:
                continue
            if message.timeout and (message.fail_time < now):
                if message.retries:
                    message.fail_time += message.timeout
                    message.retries -= 1
                    if message.retries:
                        log("retry dev_id=", self.dev_id, "mid=", message.msg_id, message.retries)
                        self.tx(message.msg)
                        return
                message.on_timeout(message)
                message.deleted = True
                return

        for i, msg in enumerate(self.messages):
            if msg.deleted:
                del self.messages[i]
                return

    def on_message(self, msg_id):
        # TODO : add lock
        #log("on_message")
        for i, message in enumerate(self.messages):
            #log("on ... ", msg_id, message.msg_id)
            if message.msg_id != msg_id:
                continue
            if message.on_ack:
                #log("on ACK !!!!!!!!!!!")
                message.on_ack()
            del self.messages[i]
            break

    def kill(self):
        self.killed = True

    def get_poll_period(self):
        return None

    def get_last_message(self):
        return self.last_response

    api = [ "report_state", "get_poll_period", "get_last_message" ]

def get_device(node):
    return devices.get(node)

#
#   Device Proxy

class DeviceProxy:

    def __init__(self, server, name):
        self.server = server
        self.name = name
        #log("Device", self.name)

    def __getattr__(self, fn_name):
        def fn(*args, **kwargs):
            return self.server.call_device(self.name, fn_name, *args, **kwargs)
        return fn

#
#

class Clock(Device):

    def __init__(self, *args, **kwargs):
        Device.__init__(self, *args, **kwargs)
        self.period = kwargs["period"]
        self.killed = False

    def run(self):
        while not self.killed:
            time.sleep(self.period)
            info = { "time" : time.time(), "scope" : "internal", }
            self.report(info)

    def kill(self):
        self.killed = True

#
#

def run_threads(runners):
    threads = []
    for target in runners:
        thread = Thread(target=target.run, name=`target`)
        if hasattr(target, "kill"):
            thread.kill = target.kill
        thread.start()
        threads.append(thread)
    return threads

def kill_threads(threads):
    for thread in threads:
        log("killing thread", `thread`)
        if hasattr(thread, "kill"):
            thread.kill()
        thread.join()
    log("all threads killed")

# FIN
