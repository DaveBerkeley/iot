#!/usr/bin/python

path = "../arduino/sketchbook/broker_talk/build-uno/broker_talk.hex"

def hex_split(line):
    for i in range(0, len(line), 2):
        yield(int(line[i:i+2], 16))

class CS:
    def __init__(self, iterator):
        self.cs = 0
        self.it = iterator
    def next(self, add=True):
        data = self.it.next()
        if add:
            self.cs += data
        return data
    def get(self):
        cs = (~self.cs) & 0xFF
        return (1 + cs) & 0xFF

def parse(line):
    assert line[0] == ":", line
    it = hex_split(line[1:])
    it = CS(it)
    size = it.next()
    addr = it.next()
    addr *= 256
    addr += it.next()
    record_type = it.next()
    data = []
    for i in range(size):
        data.append(it.next())
    cs = it.next(False)
    try:
        it.next()
        raise Exception("wrong length record")
    except StopIteration:
        pass
    csx = it.get()
    assert cs == csx, line
    assert size == len(data)
    return record_type, addr, data

#
#

of = file("/tmp/ihex.bin", "w")

for line in file(path):
    record_type, addr, data = parse(line.strip())
    print record_type, addr, data
    if record_type == 0:
        print "data ...", addr
        of.seek(addr)
        s = [ chr(c) for c in data ]
        s = "".join(s)
        of.write(s)
    elif record_type == 1:
        print "EOF"
        of.close()
    else:
        raise Exception("Unknown record type " + line)

# FIN
