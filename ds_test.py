# ds_test.py Demonstrate ways to exit from pyb.standby(): Pyboard D specific

# Copyright 2020 Peter Hinch
# This code is released under the MIT licence

# V0.43 Oct 2020
# Pyboard firmware briefly flashes the green LED on all wakeups.

import pyb
import upower
import machine
rtc = pyb.RTC()
leds = tuple(pyb.LED(x) for x in range(1, 4))  # rgb
# Light LEDs, extinguishing any not listed
def light(*these):
    any(leds[x].on() if x in these else leds[x].off() for x in range(3))

# Falling edge: need a pullup to a permanently available supply (not the switched 3V3)
# Rising edge: pull down to Gnd.
# Wakeup pins are 5V tolerant.
# pin_names: list of any of 'X1', 'X3' 'C1', 'C13'
def test(*pin_names, rising=True):
    wups = [upower.WakeupPin(pyb.Pin(name), rising=rising) for name in pin_names]
    reason = machine.reset_cause()  # Why have we woken?
    if reason in (machine.PWRON_RESET, machine.HARD_RESET, machine.SOFT_RESET):  # first boot
        rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
        upower.savetime()
        if upower.bkpram_ok():  # backup RAM holds valid data: battery backed
            light(2)  # Blue only
        else:  # Boot with no backup battery, data is garbage
            light(0, 1, 2)  # White
    elif reason == machine.DEEPSLEEP_RESET:
        reason = upower.why()
        if reason == 'WAKEUP':
            light(0, 1, 2)  # White on timer wakeup
            upower.savetime()
        elif reason == 'X3':  # red
            light(0)
        elif reason == 'X1':  # green
            light(1)
        elif reason == 'C1':
            light(2)  # Blue
        elif reason == 'C13':
            light(0, 1)  # Red and green
        else:
            upower.cprint('Unknown: reset?')  # Prints if a UART is configured

    upower.lpdelay(500)  # ensure LEDs visible before standby turns it off
    while any((p.state() for p in wups)):
        upower.lpdelay(50)  # Wait for wakeup signals to go away
    upower.lpdelay(50)  # Wait out any contact bounce

    # demo of not resetting the wakeup timer after a pin interrupt
    try:  # ms_left can fail in response to various coding errors
        timeleft = upower.ms_left(10000)
    except upower.RTCError:
        timeleft = 10000  # Coding error: uninitialised - just restart the timer
    # Set a minimum sleep duration: too short and it uses less power to stay awake
    # In real apps this might be longer or you might deal with it in other ways.
    timeleft = max(timeleft, 1000)
    rtc.wakeup(timeleft)
    # These calls reconfigure hardware and should be done last, shortly before standby()
    for p in wups:
        p.enable()
    if not upower.usb_connected:
        pyb.standby()  # Set pins hi-z and turn LEDs off
    else:
        light(1)  # Green LED: debugging session.
