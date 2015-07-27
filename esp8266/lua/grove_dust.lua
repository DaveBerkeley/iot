
dust_pin = 5 -- dust sensor

gpio.mode(dust_pin, gpio.INPUT, gpio.FLOAT)
gpio.trig(dust_pin, "both", function() end)

dust.init(dust_pin)

function get_ratio()
    lo, hi, pulses, bad = dust.read()
    if bad == 1 then
        return 0.0
    end
    if pulses < 2 then
        return 0.0
    end
    -- print(lo, hi, pulses, bad)
    ratio = lo / (lo + hi)
    return ratio / 10.0
end

function tx_data()
    local r = get_ratio()
    print (r)
    tx("wiki/iot.cgp?dust=" .. r)
end

-- send data every X ms
tmr.alarm(0, 30000, 1, function() tx_data() end )


