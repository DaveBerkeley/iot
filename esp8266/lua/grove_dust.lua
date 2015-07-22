
dust_pin = 5 -- dust sensor

gpio.mode(dust_pin, gpio.INPUT, gpio.FLOAT)
gpio.trig(dust_pin, "both", function() end)

dust.init(dust_pin)

function get_ratio()
    lo, hi, pulses, bad = dust.read()
    ratio = lo / (lo + hi)
    return ratio
end

function tx_data()
    tx("wiki/iot.cgp?dust=" .. get_ratio())
end

-- send data every X ms
tmr.alarm(0, 10000, 1, function() tx_data() end )


