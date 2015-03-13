
key = 3     -- GPIO03
gpio.mode(key, gpio.INPUT)

function on_key()
    tx("wiki/iot.cgp?key=1")
end

gpio.trig(key, "down", on_key)

