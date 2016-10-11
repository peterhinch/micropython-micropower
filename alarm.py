# alarm.py Demonstrate using RTC alarms to exit pyb.standby()

# Copyright Peter Hinch
# V0.4 10th October 2016 Now uses machine.reset_cause()
# Flashes leds at 30 second intervals courtesy of two concurrent timers
# (each times out at one minute intervals).
# Note that the Pyboard flashes the green LED briefly on waking from standby.
import stm, pyb, upower, machine

red, green, yellow, blue = (pyb.LED(x) for x in range(1, 5))
rtc = pyb.RTC()
rtc.wakeup(None) # If we have a backup battery clear down any setting from a previously running program
reason = machine.reset_cause()                           # Why have we woken?
if reason == machine.PWRON_RESET or reason == machine.HARD_RESET: # first boot
    rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
    aa = upower.Alarm('a')
    aa.timeset(second = 39)
    ab = upower.Alarm('b')
    ab.timeset(second = 9)
    red.on()
elif reason == machine.DEEPSLEEP_RESET:
    reason = upower.why()
    if reason == 'ALARM_A':
        green.on()
    elif reason == 'ALARM_B':
        yellow.on()

upower.lpdelay(1000)     # Let LED's be seen!
pyb.standby()
