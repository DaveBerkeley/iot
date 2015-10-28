#!/usr/bin/python

#
#   Read IntelHex file and generate binary file.
#
#   see : https://en.wikipedia.org/wiki/Intel_HEX

#
#   Split ASCII Hex bytes into binary numbers.

def hex_split(line):
    for i in range(0, len(line), 2):
        yield(int(line[i:i+2], 16))

#
#   Wrap iterator and provide checksum calc.

class CS:
    def __init__(self, iterator):
        self.cs = 0
        self.it = iterator
    def next(self):
        data = self.it.next()
        self.cs += data
        return data
    def get(self):
        # 2's complement
        return (1 + ~self.cs) & 0xFF

#
#   Read IntelHex line and convert into :
#   (record_type, addr, data).

def parse(line):
    assert line[0] == ":", line
    hit = hex_split(line[1:])
    it = CS(hit)
    size = it.next()
    addr = it.next()
    addr *= 256
    addr += it.next()
    record_type = it.next()
    data = []
    for i in range(size):
        data.append(it.next())
    cs = hit.next()
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

def convert(path, ofile, verbose=False):
    for line in file(path):
        record_type, addr, data = parse(line.strip())
        if verbose:
            print record_type, addr, data
        if record_type == 0:
            if verbose:
                print "data ...", addr
            ofile.seek(addr)
            s = [ chr(c) for c in data ]
            s = "".join(s)
            ofile.write(s)
        elif record_type == 1:
            if verbose:
                print "EOF"
            #ofile.close()
        else:
            raise Exception("Unknown record type " + line)

#
#

if __name__ == "__main__":
    path = "../arduino/sketchbook/radio_relay/build-uno/radio_relay.hex"
    of = file("/tmp/ihex.bin", "w")
    convert(path, of, True)

# FIN
