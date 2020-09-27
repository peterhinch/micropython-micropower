# The upower module

See also [hardware](./HARDWARE.md) for a document discussing hardware issues and
power draw calculations and measurements. This document is based on the Pyboard
V1.0, V1.1 and D series. The other platforms based on the STM chips may have
different hardware functionality. This applies to the Pyboard Lite which
supports only a subset.

# The Pyboard D

There is currently an issue with Pyboard D firmware which precludes the use of
the X1 pin to recover from standby. This is subject to
[this PR](https://github.com/micropython/micropython/pull/6494). This is
problematic because the other hardware wakeup is via pin X18 which is only
available on the wbus and WBUS_DIP68 adaptor. A solution is to build from this
PR. Alternatively replace `ports/stm32/powerctrl.c` with that in the `d_series`
directory and rebuild.

## Introduction

This module provides access to features of the Pyboard which are useful in low
power applications but not supported in firmware at the time of writing: check
for official support for any specific feature before using. Access to the
following processor features is provided:

 1. 4KB of backup RAM (optionally battery-backed) - accessible as words or bytes.
 2. 20 general purpose 32-bit registers also battery backed.
 3. Wakeup from standby by means of two Pyboard pins.
 4. Wakeup by means of two independent real time clock (RTC) alarms.
 5. Access to board voltages and CPU temperature without the drawbacks of
 `ADCAll`.

Utility functions provide a way to determine the reason for a wakeup and offer a
low power alternative to the official `delay()` function.

All code is released under the [MIT license](./LICENSE)

## Test scripts

 1. `alarm.py` Illustrates wakeup from two RTC alarms.
 2. `ttest.py` Wakes up periodically from an RTC alarm. Can be woken by linking
 pin X18 to Gnd or linking pin X1 to 3V3. Note that on the Pyboard D the latter
 requires a modified firmware build as described above.
 3. `ds_test.py` Tests the Pyboard D specific `WakeupPin` class.

The `ttest` script illustrates a means of ensuring that the RTC alarm operates
at fixed intervals in the presence of pin wakeups.

## A typical application

When a Pyboard goes into standby its consumption drops to about 6μA. When it is
woken, program execution begins as if the board had been initially powered up:
`boot.py` then `main.py` are executed. Unless `main.py` imports your
application, a REPL prompt will result. Assuming your application is re-run,
there are ways to retain some program state and to determine the cause of the
wakeup. Mastering these enables practical applications to be developed. The
following is one of the demo programs `alarm.py` which uses the two timers to
wake the Pyboard alternately, each once per minute.

```python
import stm, pyb, upower, machine

red, green, yellow = (pyb.LED(x) for x in range(1, 4))  # LED(3) is blue, not yellow, on D series
rtc = pyb.RTC()
rtc.wakeup(None) # If we have a backup battery clear down any setting from a previously running program
reason = machine.reset_cause()  # Why have we woken?
if reason == machine.PWRON_RESET or reason == machine.HARD_RESET: # first boot
    rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only
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
```

## Module description

The module uses the topmost three 32 bit words of the backup RAM (1021-1923
inclusive).

Note on objects in this module. Once `rtc.wakeup()` is issued, methods other
than `enable()` should be avoided as some employ the RTC. Issue `rtc.wakeup()`
shortly before `pyb.standby`.

### Globals

The module provides a single global variable:  
`usb_connected` A boolean, `True` if REPL via USB is enabled and a physical
USB connection is in place. On the Pyboard 1.x this returns `True` if power is
supplied from the USB connector. On the D series it returns `True` only if a
terminal session is running on the USB connector.

### Principal functions

The module provides the following functions:  
 1. `lpdelay` A low power alternative to `pyb.delay()`.
 2. `lp_elapsed_ms` An alternative to `pyb.elapsed_millis` which works
 during `lpdelay` calls.
 3. `now` Returns RTC time in millisecs since the start of year 2000.
 4. `savetime` Store current RTC time in backup RAM. Optional arg `addr`
 default 1021 (uses 2 words).
 5. `ms_left` Enables a timed sleep or standby to be resumed after a tamper or
 WKUP interrupt.
 Requires `savetime` to have been called before commencing the sleep/standby.
 Arguments `delta` the delay period in ms, `addr` the address where the time
 was saved (default 1021).
 6. `cprint` Same usage as `print` but does nothing if USB is connected.
 7. `why` No args. Returns the reason for a wakeup event.
 8. `bkpram_ok` No args. Detection of valid data in backup RAM after a
 power up event. Returns `True` if RAM has retained data (i.e. it was battery
 backed during outage).

### Other functions

These functions were implemented to overcome a problem with the `pyb.ADCAll`
class. This has been fixed but the functions are retained to avoid breaking
code.  
 1. `v33` No args. Returns Vdd. If Vin > 3.3V Vdd should read approximately
 3.3V.  Lower values indicate a Vin which has dropped below 3.3V typically due
 to a failing battery.
 2. `vref` Returns the reference voltage.
 3. `vbat` Returns the backup battery voltage (if fitted).
 4. `temperature` Returns the chip temperature in °C. Note that the chip
 datasheet points out  that the absolute accuracy of this is poor, varies
 greatly from one chip to another, and is best suited for monitoring changes in
 temperature. It produces spectacularly poor results if the 3.3V supply drops
 out of spec.

### Classes

The module provides the following classes:  
 1. `Alarm` Provides access to the two RTC alarms.
 2. `BkpRAM` Provides access to the backup RAM.
 3. `RTC_Regs` Provides access to the backup registers.
 4. `Tamper` Enables wakeup from the Tamper pin X18 (C13, W26 on Pyboard D).
 5. `wakeup_X1` Enables wakeup from a positive edge on pin X1.

## Function `lpdelay()`

This function accepts one argument: a delay in ms and is a low power replacement
for `pyb.delay()`. The function normally uses `pyb.stop` to reduce power
consumption from 20mA to 500μA. If USB is connected it reverts to `pyb.delay`
to avoid killing the USB connection. There is a subtle issue when using this
function: `pyb` loses all sense of time when the Pyboard is stopped.
Consequently you can't use functions such as `pyb.elapsed_millis` to keep
track of time in a loop. The simplest solution is to use the provided
`lp_elapsed_ms` function.

## Function `lp_elapsed_ms()`

Accepts one argument, a start time in ms from the `now` function. Typical code
to implement a one second timeout might be along these lines:

```python
start = upower.now()
while upower.lp_elapsed_ms(start) < 1000:
    print(upower.lp_elapsed_ms(start)) # do something
    upower.lpdelay(100)
```

## Function `now()`

Returns RTC time in milliseconds since the start of year 2000. The function is
mainly intended for use in implementing sleep or standby delays which can be
resumed after an interrupt from tamper or WKUP. Millisecond precision is
meaningless in standby periods where wakeups are slow, but is relevant to sleep.
Precision is limited to about 4ms owing to the RTC hardware.

## Function `savetime()`

Store current RTC time in backup RAM. Optional argument `addr` default 1021.
This uses two words to store the milliseconds value produced by `now()`

## Function `ms_left()`

This produces a value of delay for presenting to `wakeup()` and enables a
timed sleep or standby to be resumed after a tamper or WKUP interrupt. To use
it, execute `savetime` before commencing the sleep/standby. Arguments `delta`
normally the original delay period in ms, `addr` the address where the time
was saved (default 1021). The function can raise an exception in response to a
number of errors such as the case where a time was not saved or the RTC was
adjusted after saving. The defensive coder will trap these!

If the time has expired it will return zero (i.e. it will never return negative
values).

The test program `ttest.py` illustrates its use.

## Function `why()`

This enhances `machine.reset_cause` by providing more detail on the reason
why the Pyboard has emerged from deep sleep. `machine.reset_cause` should
first be called to detect the conditions `PWRON_RESET` or `HARD_RESET`.
If it returns `DEEPSLEEP_RESET` then `why()` may be called. It will
return one of the following values:

 1. 'TAMPER' Woken by the Tamper pin (X18) (C13, W26 on Pyboard D).
 2. 'WAKEUP' Woken by RTC.wakeup().
 3. 'ALARM_A' Woken by RTC alarm A.
 4. 'ALARM_B' Woken by RTC alarm B.
 5. 'X1' Woken by the WKUP pin (X1).
 6. `None` Reason unknown.

## Alarm class (access RTC alarms)

The RTC supports two alarms 'A' and 'B' each of which can wake the Pyboard at
programmed intervals.

Constructor: an alarm is instantiated with a single mandatory argument, 'A' or
'B'.  
Method `timeset()` Assuming at least one kw only argument is passed, this will
start the timer and cause periodic interrupts to be generated. In the absence of
arguments the timer will be disabled. Arguments default to `None`.  
Arguments (kwonly args):  
 1. `day_of_month` 1..31 If present, alarm will occur only on that day
 2. `weekday` 1 (Monday) - 7 (Sunday) If present, alarm will occur only on
 that day of the week
 3. `hour` 0..23
 4. `minute` 0..59
 5. `second` 0..59

Usage examples:  
mytimer.timeset(weekday = 1, hour = 17) # Wake at 17:00 every Monday  
mytimer.timeset(hour = 5) # Wake at 5am every day  
mytimer.timeset(minute = 10, second = 30) # Wake up every hour at 10 mins, 30
secs after the hour  
mytimer.timeset(second = 30) # Wake up each time RTC seconds reads 30 i.e. once
per minute  

## BkpRAM class (access Backup RAM)

This class enables the on-chip 4KB of battery backed RAM to be accessed as an
array of integers or as a bytearray. The latter facilitates creating persistent
arbitrary objects using JSON or pickle.
Its initial contents after power up are arbitrary unless an RTC backup battery
is used. Note that `savetime()` uses two 32 bit words at 1021 and 1022 by
default and startup detection uses 1023 so these top three locations should
normally be avoided.

```python
from upower import BkpRAM
bkpram = BkpRAM()
bkpram[0] = 22 # use as integer array
bkpram.ba[4] = 0 # or as a bytearray
```

The following code fragment illustrates the use of pickle to save an arbitrary
Python object to backup RAM and restore it on a subsequent wakeup. The pickle
module is available in the MicroPython library.

```python
import pickle, upower
bkpram = upower.BkpRAM()
a = {'rats':77, 'dogs':99,'elephants':9, 'zoo':100}
z = pickle.dumps(a).encode('utf8')
bkpram[0] = len(z)
bkpram.ba[4: 4+len(z)] = z # Copy into backup RAM
 # Resumption after standby
import pickle, upower
bkpram = upower.BkpRAM()
 # retrieve dictionary
a = pickle.loads(bytes(bkpram.ba[4:4+bkpram[0]]).decode('utf-8'))
```

## RTCRegs class (RTC Register access)

The RTC has a set of 20 32-bit backup registers. These are initialised to zero
on boot, and are also cleared down after a Tamper event. Registers may be
accessed as follows:  

```python
from upower import RTCRegs
rtcregs = RTCRegs()
rtcregs[3] = 42
```

## Tamper class (Enable wakeup on pin X18 (C13, W26 on Pyboard D))

This is a flexible way to interrupt a standby condition, providing for edge or
level detection, the latter with hardware switch debouncing. Level detection
operates as follows. The pin is normally high impedance. At intervals a pullup
resistor is connected and the pin state sampled. After a given number of such
intervals, if the pin continues to be in the active state, the Pyboard is woken.
The active state, polling frequency and number of samples may be configured
using `tamper.setup()`.

Note that in edge triggered mode the pin behaves as a normal input with no
pullup. If driving from a switch, you must provide a pullup (to 3V3) or pulldown
as appropriate.

In use first instatiate the tamper object:

```python
from upower import Tamper
tamper = Tamper()
```

The class supports the following methods and properties.  

`setup()` method accepts the following arguments:
 1. `level` Mandatory: valid options 0 or 1. In level triggered mode,
 determines the active level.
 In edge triggered mode, 0 indicates rising edge trigger, 1 falling edge.
 Optional kwonly args:
 2. `freq ` Valid options 1, 2, 4, 8, 16, 32, 64, 128: polling frequency in
 Hz. Default 16.
 3. `samples` Valid options 2, 4, 8: number of consecutive samples before
 wakeup occurs. Default 2.
 4. `edge` Boolean. If True, the pin is edge triggered. `freq` and
 `samples` are ignored. Default False.

`enable()` method enables the tamper interrupt. Call just before issuing
`pyb.standby()` and after the use of any other methods as it reconfigures the
pin.

`tamper.wait_inactive()` method returns when pin X18 has returned to its
inactive state. In level triggered mode this may be called before issuing the
`enable()` method to avoid recurring interrupts. In edge triggered mode where
the signal is from a switch it might be used to debounce the trailing edge of
the contact period.

`disable()` method disables the interrupt. Not normally required as the
interrupt is disabled by the constructor.

`pinvalue` property returning the value of the signal on the pin: 0 is 0V
regardless of `level`.

See `ttest.py` for an example of its usage.

## wakeup_X1 class (Enable wakeup on pin X1)

Enabling this converts pin X1 into an input with a pulldown resistor enabled
even in standby mode. A low to high transition will wake the Pyboard from
standby. The following code fragment illustrates its use. A complete example is
in `ttest.py`.

```python
from upower import wakeup_X1
wkup = wakeup_X1()
  # code omitted
wkup.enable()
if not upower.usb_connected:
    pyb.standby()
```

The `wakeup_X1` class has the following methods and properties.

`enable()` enables the wkup interrupt. Call just before issuing `pyb.standby()`
and after the use of any other wkup methods as it reconfigures the pin.

`wait_inactive()` This method returns when pin X1 has returned low. This might
be used to debounce the trailing edge of the contact period: call `lpdelay(50)`
after the function returns and before entering standby to ensure that contact
bounce is over.

`disable()` disables the interrupt. Not normally required as the interrupt is
disabled by the constructor.

`pinvalue` Property returning the value of the signal on the pin: 0 is low, 1
high.

## WakeupPin class (Pyboard D only)

The Pyboard D can wake from standby by means of inputs on the following pins.
Note the pin name aliases:
 1. `A0   X1  W19`
 2. `A2   X3  W15`
 3. `C1       W24`
 4. `C13      W26`

It does not seem to be possible to configure the internal pullups or pull-downs
in this mode, so if switches are used an external resistor must be supplied.
Wakeups may be on a rising or falling transition.

Constructor:  
This takes two args, a `Pin` instance and `rising=True`. The `Pin` instance
does not need to be configured. If `rising` is `True`, wakeup will occur on a
low to high transition. A `ValueError` will result if the host is not a Pyboard
D or if the `Pin` instance is not one of the above pins.

Methods:  
 1. `enable()` enables the wkup interrupt. Call just before issuing
 `pyb.standby()` and after the use of any other wkup methods as it reconfigures
 the pin.
 2. `wait_inactive()` This method returns when the pin has returned to the
 inactive state. This might be used to debounce a switch contact: call
 `lpdelay(50)` after the function returns and before entering standby to ensure
 that contact bounce is over.
 3. `disable()` disables the interrupt. Not normally required as the interrupt
 is disabled by the constructor.

Property:  
 1. `pinvalue` Returns the value of the signal on the pin: 0 is low, 1 high.

# Module ttest

Demonstrates various ways to wake up from standby and how to differentiate
between them.

To run this, edit your `main.py` to include `import ttest`. Power the
Pyboard from a source other than USB. It will flash the red, yellow and green
LEDs after boot and the green and yellow ones every ten seconds in response to a
timer wakeup. If pin X1 is pulled to 3V3 red and green will flash. If pin X18
(C13, W26 on Pyboard D) is pulled low red will flash. If a backup battery is in
use and power to the board is cycled, power up events subsequent to the first
will cause the yellow LED to flash.

If a UART is initialised for REPL in boot.py the time of each event will be
output.

If an RTC backup battery is used and the Pyboard power is removed while a wakeup
delay is pending it will behave as follows. If power is re-applied before the
delay times out, it will time out at the correct time. If power is applied after
the time has passed two wakeups will occur soon after power up: the first caused
by the power up, and the second by the deferred wakeup.

# Module alarm

Demonstrates the RTC alarms. Runs both alarms concurrently, waking every 30
seconds and flashing LED's to indicate which timer has caused the wakeup. To run
this, edit your `main.py` to include `import alarm`.

# Coding tips

## Debugging using print()

Using USB for the REPL makes this impractical because `stop()` and `standby()`
break the connection. A solution is to redirect the REPL to a UART and use a
terminal application via a USB to serial adaptor. If your code uses `standby()`
a delay may be necessary prior to the call to ensure sufficient time elapses for
the data to be transmitted before the chip shuts down.

On resumption from standby the Pyboard will execute `boot.py` and `main.py`,
so unless `main.py` restarts your program, you will be returned to the REPL.

Other points to note when debugging code which uses standby mode. If using a
backup battery the RTC will remember settings even if the Pyboard is powered
down. So if you run `rtc.wakeup(value)`, power down the board, then power it
up to run another program, it will continue to wake from standby at the interval
specified. Issue `rtc.wakeup(None)` if this is not the desired outcome. The
same applies to alarms: to clear down an alarm instantiate it and issue its
`timeset()` method with no arguments.

Another potential source of confusion arises if you use `rshell` to access the
Pyboard. Helpfully it automatically sets the RTC from the connected computer.
However it can result in unexpected timings if the RTC is adjusted when delays
or alarms are pending.

## CPU clock speed

When coding for minimum power consumption there are various options. One is to
reduce the CPU clock speed: its current draw in normal running mode is roughly
proportional to clock speed. However in computationally intensive tasks the
total charge drawn from a battery may not be reduced since processing time will
double if the clock rate is halved. This is a consequence of the way CMOS logic
works: gates use a fixed amount of charge per transition. If your code spends
time waiting on `pyb.delay()` reducing clock rate will help, but if using
`upower.lpdelay()` gains may be negligible.
