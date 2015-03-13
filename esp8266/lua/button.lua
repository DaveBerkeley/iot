
key = 3     -- GPIO03
gpio.mode(key, gpio.INPUT)

function key_enable(handler)
    gpio.trig(key, "down", handler)
end

function on_key()
    -- implement debounce by ignoring presses for a period
    key_enable(function() end)
    tx("wiki/iot.cgp?key=1")
    tmr.alarm(1, 250, 0, function() key_enable(on_key) end)
end

key_enable(on_key)

