

class SyntaxError(Exception):
    pass

def encode_(s, data):
    if type(data) == type([]):
        s.append('l')
        for d in data:
            encode_(s, d)
        s.append('e')
    elif type(data) == type(123):
        s.append('i%de' % data)
    elif type(data) == type("abc"):
        s.append('%d:%s' % (len(data), data))
    else:
        raise Exception("not implemented yet")

def encode(data):
    s = []
    encode_(s, data)
    return "".join(s)

#
#

class Parser:

    def __init__(self, readfn):
        self.readfn = readfn

    def parse(self, c):
        if c == 'i':
            # integer
            num = 0
            mul = 1
            c = self.readfn()
            if c == '-':
                mul = -1
                c = self.readfn()
            while True:
                if c == 'e':
                    return num * mul
                elif '0' <= c <= '9':
                    num *= 10
                    num += ord(c) - ord('0')
                else:
                    raise SyntaxError()
                c = self.readfn()
                
        if c == 'l':
            # list
            data = []
            while True:
                c = self.readfn()
                if c == 'e':
                    return data
                data.append(self.parse(c))
                
        if '0' <= c <= '9':
            # string
            length = ord(c) - ord('0')
            while True:
                c = self.readfn()
                if c == ':':
                    break;
                if '0' <= c <= '9':
                    length *= 10
                    length += ord(c) - ord('0')
            data = []
            for i in range(length):
                data.append(self.readfn())
            return "".join(data)

        if c == 'd':
            raise Exception("not implemented yet")

        raise SyntaxError()

    def get(self):
        return self.parse(self.readfn())

# FIN
