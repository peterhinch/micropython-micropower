# ttest.py Demonstrate ways to exit from pyb.standby()

# Copyright 2016-2020 Peter Hinch
# This code is released under the MIT licence

# V0.43 Oct 2020 Tested on Pyboard D
# V0.4 10th October 2016 Now uses machine.reset_cause()

# draws 32uA between LED flashes runing from flash.
# This doesn't do much running from USB because the low power modes kill the USB interface.
# Pyboard 1.x: 
# the blue LED is best avoided in these applications as it currently uses PWM: this can
# lead to some odd effects in time dependent applications.
# Pyboard D:
# LED[3] described as yellow is actually blue.
# All boards:
# Pyboard firmware briefly flashes the green LED on all wakeups.

import pyb, upower, machine
tamper = upower.Tamper()
wkup = upower.wakeup_X1()
tamper.setup(level = 0, freq = 16, samples = 2, edge = False) # A level of zero triggers
#upower.tamper.setup(level = 1, edge = True) # Falling edge trigger. You must supply a pullup resistor.
rtc = pyb.RTC()

leds = tuple(pyb.LED(x) for x in range(1, 4))   # rgy
for led in leds:
    led.off()

reason = machine.reset_cause()                  # Why have we woken?
if reason in (machine.PWRON_RESET, machine.HARD_RESET, machine.SOFT_RESET): # first boot
    rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
    upower.savetime()
    if upower.bkpram_ok():                      # backup RAM holds valid data
        leds[2].on()                            # Y only
    else:                                       # No backup battery, data is garbage
        for led in leds:
            led.on()                            # RGY == 1st boot
elif reason == machine.DEEPSLEEP_RESET:
    reason = upower.why()
    if reason == 'WAKEUP':                      # green and yellow on timer wakeup
        leds[1].on()
        leds[2].on()
        upower.savetime()
    elif reason == 'TAMPER':                    # red
        leds[0].on()
    elif reason == 'X1':                        # red and green on X1 rising edge
        leds[0].on()
        leds[1].on()
    else:
        upower.cprint('Unknown: reset?')        # Prints if a UART is configured

t = rtc.datetime()[4:7]
upower.cprint('{:02d}.{:02d}.{:02d}'.format(t[0],t[1],t[2]))

upower.lpdelay(500)                             # ensure LED visible before standby turns it off

tamper.wait_inactive()                          # Wait for tamper signal to go away
wkup.wait_inactive()
upower.lpdelay(50)                              # Wait out any contact bounce
                                                # demo of not resetting the wakeup timer after a pin interrupt
try:                                            # ms_left can fail in response to various coding errors
    timeleft = upower.ms_left(10000)
except upower.RTCError:
    timeleft = 10000                            # Coding error: uninitialised - just restart the timer
timeleft = max(timeleft, 1000)                  # Set a minimum sleep duration: too short and it uses less power to stay awake
                                                # In real apps this might be longer or you might deal with it in other ways.
rtc.wakeup(timeleft)
# These calls reconfigure hardware and should be done last, shortly before standby()
tamper.enable()
wkup.enable()
if not upower.usb_connected:
    pyb.standby()                               # This will set pins hi-z and turn LEDs off
else:
    for led in leds:
        led.off()
    leds[1].on()  # Green LED: debugging session.
