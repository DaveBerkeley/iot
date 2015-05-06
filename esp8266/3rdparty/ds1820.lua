
-- Measure temperature
-- 2014 OK1CDJ
--- see https://github.com/ok1cdj

temperature_pin = 5 -- GPIO14

ow.setup(temperature_pin)

function bxor(a,b)
   local r = 0
   for i = 0, 31 do
      if ( a % 2 + b % 2 == 1 ) then
         r = r + 2^i
      end
      a = a / 2
      b = b / 2
   end
   return r
end

--- Get temperature from DS18B20 
function getTemp(temperature_pin)
    addr = ow.reset_search(temperature_pin)
    repeat
        tmr.wdclr()

        if (addr ~= nil) then
            crc = ow.crc8(string.sub(addr,1,7))
            if (crc == addr:byte(8)) then
                if ((addr:byte(1) == 0x10) or (addr:byte(1) == 0x28)) then
                    ow.reset(temperature_pin)
                    ow.select(temperature_pin, addr)
                    ow.write(temperature_pin, 0x44, 1)
                    tmr.delay(1000000)
                    present = ow.reset(temperature_pin)
                    ow.select(temperature_pin, addr)
                    ow.write(temperature_pin,0xBE, 1)
                    data = nil
                    data = string.char(ow.read(temperature_pin))
                    for i = 1, 8 do
                        data = data .. string.char(ow.read(temperature_pin))
                    end
                    crc = ow.crc8(string.sub(data,1,8))
                    if (crc == data:byte(9)) then
                        t = (data:byte(1) + data:byte(2) * 256)
                        if (t > 32768) then
                            t = (bxor(t, 0xffff)) + 1
                            t = (-1) * t
                        end
                        t = t * 625
                        return t
                        -- print("" .. (t / 10000.0) .. " C")
                    end                   
                    tmr.wdclr()
                end
            end
        end
        addr = ow.search(temperature_pin)
    until(addr == nil)
end

function txTemp()
    t = getTemp(temperature_pin)
    tx("wiki/iot.cgp?temp=" .. (t / 10000.0))
end

-- send data every X ms
tmr.alarm(0, 60000, 1, function() txTemp() end )

