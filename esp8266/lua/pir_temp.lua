
function txTemp()
    local t = getTemp(temperature_pin)
    tx("wiki/iot.cgp?temp=" .. (t / 10000.0))
end

-- send data every X ms
tmr.alarm(0, 60000, 1, function() txTemp() end )

