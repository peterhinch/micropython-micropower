# ds_test.py Demonstrate ways to exit from pyb.standby(): Pyboard D specific

# Copyright 2020 Peter Hinch
# This code is released under the MIT licence

# V0.43 Oct 2020
# Pyboard firmware briefly flashes the green LED on all wakeups.

import pyb, upower, machine
# Falling edge: need a pullup to a permanently available supply (not the switched 3V3)
# Rising edge: pull down to Gnd.
# Wakeup pins are 5V tolerant.
wx1 = upower.WakeupPin(pyb.Pin('X1'), rising=True)
wx3 = upower.WakeupPin(pyb.Pin('X3'), rising=True)
wxc1 = upower.WakeupPin(pyb.Pin('C1'), rising=True)

rtc = pyb.RTC()

leds = tuple(pyb.LED(x) for x in range(1, 4))  # rgb
any(led.off() for led in leds)

reason = machine.reset_cause()  # Why have we woken?
if reason in (machine.PWRON_RESET, machine.HARD_RESET, machine.SOFT_RESET): # first boot
    rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
    upower.savetime()
    if upower.bkpram_ok():  # backup RAM holds valid data: battery backed
        leds[2].on()  # Blue only
    else:  # Boot with no backup battery, data is garbage
        any(led.on() for led in leds)
elif reason == machine.DEEPSLEEP_RESET:
    reason = upower.why()
    if reason == 'WAKEUP':  # White on timer wakeup
        any(led.on() for led in leds)
        upower.savetime()
    elif reason == 'X3':  # red
        leds[0].on()
    elif reason == 'X1':  # green
        leds[1].on()
    elif reason == 'C1':
        leds[2].on()  # Blue
    else:
        upower.cprint('Unknown: reset?')  # Prints if a UART is configured

t = rtc.datetime()[4:7]
upower.cprint('{:02d}.{:02d}.{:02d}'.format(t[0],t[1],t[2]))

upower.lpdelay(500)  # ensure LED visible before standby turns it off

wx1.wait_inactive()  # Wait for wakeup signals to go away
wx3.wait_inactive()
wxc1.wait_inactive()
upower.lpdelay(50)  # Wait out any contact bounce

# demo of not resetting the wakeup timer after a pin interrupt
try:  # ms_left can fail in response to various coding errors
    timeleft = upower.ms_left(10000)
except upower.RTCError:
    timeleft = 10000  # Coding error: uninitialised - just restart the timer
timeleft = max(timeleft, 1000)  # Set a minimum sleep duration: too short and it uses less power to stay awake
# In real apps this might be longer or you might deal with it in other ways.
rtc.wakeup(timeleft)
# These calls reconfigure hardware and should be done last, shortly before standby()
wx1.enable()
wx3.enable()
wxc1.enable()
if not upower.usb_connected:
    pyb.standby()                               # This will set pins hi-z and turn LEDs off
else:
    for led in leds:
        led.off()
    leds[1].on()  # Green LED: debugging session.
