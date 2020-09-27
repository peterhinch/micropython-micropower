# Minimising Pyboard system power consumption

This document covers Pyboard hardware V1.0, V1.1 and D series. Users of V1.0
Pyboards should note that the standby current of this version is approximately
30μA as against 6μA for later versions.

See also [upower](./UPOWER.md) for a Python module providing access to SOC
resources of use in low power systems.

All code is issued under the [MIT license](./LICENSE)

# Abstract

These notes describe some issues involved in minimising power draw in Pyboard
based systems. In the case of Pyboard 1.x external circuitry can reduce
consumption when the Pyboard is used with external chips or modules. A circuit
design and PCB layout are offered for achieving this; it was specifically
designed for an e-paper display and the NRF24L01 radio, but it could readily
be used with other devices. Some calculations are presented suggesting limits
to the runtimes that might be achieved from various types of batteries.

The power overheads of the Pyboard are discussed and measurements presented.
These overheads comprise the standby power consumption and the charge required
to recover from standby and to load and compile typical application code.

# The Pyboard D series

The Pyboard D has an improved design, so external circuitry is not usually
required. This is because the D series has a 3.3V regulator which is software
switchable and may be used to control the power to peripherals and to I2C
pullups. It is turned on by
```python
machine.Pin.board.EN_3V3.value(1)  # 0 to turn off
```
The parts of this document detailing external circuitry and the module
`micropower.py` may be ignored for the D series. General observations about
nonvolatile storage, SD cards and power calculations remain relevant.

## Use cases

I have considered two types of use case. The first is a monitoring application
which periodically wakes, reads data from a sensor then returns to standby. At
intervals it uses an NRF24L01 radio to send the accumulated data to a remote
host. The second is a remote display using the NRF24L01 to acquire data from a
remote host and an e-paper display to enable this to be presented when the
Pyboard is in standby. In either case the Pyboard might be battery powered or
powered from a power constrained source such as solar photovoltaic cells.

## Standby mode

To achieve minimum power the code must be designed so that the Pyboard spends
the majority of its time in standby mode. In this mode the current drawn by the
Pyboard drops to some 6μA. Note that on recovery from standby the code will be
loaded and run from the start: program state is not retained. Limited state
information can be retained in the RTC backup registers: in the example below
one is used to detect whether the program has run because of an initial power
up or in response to an RTC interrupt. A typical application will use code
along these lines:

```python
import pyb, stm
rtc = pyb.RTC()

usb_connected = False
if pyb.usb_mode() is not None:  # User has enabled CDC in boot.py
    usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
    if not usb_connected:  # Not physically connected
        pyb.usb_mode(None)  # Save power

if stm.mem32[stm.RTC + stm.RTC_BKP1R] == 0:  # first boot
   rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0))  # Code to run on 1st boot only

 # code to run every time goes here
rtc.wakeup(20000)
stm.mem32[stm.RTC + stm.RTC_BKP1R] = 1  # indicate that we are going into standby mode
if not usb_connected:
   pyb.standby()
```

Note that this code does not use the `upower` module which would simplify it.
The intention here is to illustrate the principles of low power operation.

The `usb_connected` logic simplifies debugging using a USB cable while
minimising power when run without USB. The first boot detection is a
potentially useful convenience. In general debugging micropower applications is
simplified by using a UART rather than USB: this is strongly recommended and is
discussed below.

There are four ways to recover from standby: an RTC wakeup, RTC alarm wakeup, a
tamper pin input, and a wakeup pin input. These are supported in `upower.py`.

## Nonvolatile memory and storage in standby

To achieve the 6μA standby current it is necessary to use the internal flash
memory for program storage rather than an SD card as SD cards draw significant
standby current. The value varies with manufacturer but tends to dwarf the
current draw of the Pyboard - 200μA is common. 

Some applications will require data to be retained while the Pyboard is in
standby. Very small amounts may be stored in the RTC backup registers. The
Pyboard also has 4KB of backup RAM which is more flexible and also retains data
in standby. Code for using these options is provided below.

In systems requiring true nonvolatile storage where data is retained after
power loss as well as during standby one option is to use files in the internal
flash, but this raises the issue of endurance. The Flash is rated at 10,000
writes, a figure which is approached in a year even if the Pyboard only wakes
and writes to it hourly (this is greatly mitigated by the littlefs filesystem).

There are various high endurance nonvolatile memory technologies such as EEPROM
and FRAM. Drivers for these may be found [here](https://github.com/peterhinch/micropython_eeprom). 

Larger volumes of data could be stored in an SD card whose power can be
controlled as required: MicroPython supports an sdcard driver module enabling a
card in an SPI adapter to be mounted in the filesystem. While lacking the
extreme endurance of FRAM it should offer an effective solution in most
applications, with power switching overcoming the "always on" power use of the
inbuilt SD card connector.

# Hardware issues

Most practical applications will have hardware peripherals connected to Pyboard
GPIO pins and the various Pyboard interfaces. To conserve power these should be
powered down when the Pyboard is in standby. The Pyboard D enables this by
means of a sofware-switchable 3.3V regulator. The Pyboard 1.x provides no means
of doing this. In principle this could be achieved thus:

![Schematic](simple_schem.jpg)

On first boot or on leaving standby the code drives the pin low, then drives it
high before entering standby. In this state the GPIO pins go high impedance, so
the MOSFET remains off by virtue of the resistor.

On Pyboard 1.x this is inadequate for devices using the I2C bus or using the
I2C pins as GPIO. This is because the Pyboard has pullup resistors on these
pins which will source current into the connected hardware even when the latter
is powered down. The simplest solution is to switch Vdd as in the above
schematic and also to provide switches in series with the relevant GPIO pins to
enable them to be put into a high impedance state. The current consumed by the
connected hardware when the Pyboard is in standby is then negligible compared
to the total current draw of 6μA.

This problem is solved on the Pyboard D in that the I2C pullups for I2C(1) are
powered from the switched 3.3V supply. I2C(2) has no pullups: these must be
provided if this interface is to be used.

A 6μA power consumption offers the possibility of a year's operation from a
CR2032 button cell. In practice achieving this is dependent on the frequency
and duration of power up events.

## Pyboard 1.x circuit design

The following design provides for switching as described above and also - by
virtue of a PCB design - simplifies the connection of the Pyboard to an e-paper
display and the NRF24L01. Connections are provided for other I2C devices namely
ferroelectric RAM (FRAM) [modules](https://learn.adafruit.com/adafruit-i2c-fram-breakout)
and a BMP180 pressure sensor although these pins may readily be employed for
other I2C modules.

The design uses two Pyboard pins to control the peripheral power and the pullup
resistors. Separate control is preferable because it enables devices to be
powered off prior to disabling the pullups, which is recommended for some
peripherals. An analog switch is employed to disable the pullup resistors.

Resistors R3, R4 and capacitor C1 are optional and provide the facility for a
switched filtered or slew rate limited 3.3V output. This was provided for the
FRAM modules which specify a minimum and maximum slew rate: for these fit R3
and R4. In this instance C1 may be omitted as the modules have a 10μF capacitor
onboard.

![Schematic](epd_vddonly_schem.jpg)

An editable version is provided in the file epd_vddonly.fzz - this requires the
free (as in beer) software from [Fritzing](http://fritzing.org/home/) where
PCB's can be ordered. The Fritzing software can produce extended Gerber files
for those wishing to producure boards from other suppliers.

I have an alternative version which replaces the FRAM with a power switched
MicroSD card socket and provides a connector for an FTDI serial cable on UART4.
I can provide details on request.
 
## Pyboard 1.x Driver micropower.py

This is generalised to provide for hardware using a one or two pins to control
power and pullups. If two pins are specified it assumes that the active high
pin controls the pullups and the active low pin controls power as per the above
schematic. If a single pin is specified it is taken to control both.

The driver supports a single class `PowerController`

### Methods

`PowerController()` The constructor has two arguments being strings
representing Pyboard pins. If either is `None` it is assumed to control power
and pullups. Arguments:
 1. `pin_active_high` Driven high in response to `power_up()`. If both pins are
 defined powers I2C pullups.
 2. `pin_active_low` Driven low in response to `power_up()`. If both pins are
 defined powers peripherals.

`power_up()` No arguments. Powers up the peripherals, waits for power to settle
before returning.
`power_down()` No arguments. Powers down the peripherals. Waits for power to
decay before powering down the I2C pullups and de-initialising the buses (the
I2C driver seems to require this).

### Property

`single_ended` Boolean: True if the PowerController has separate control of
power and pullups.

The driver provides optional support for use as a context manager thus:

```python
from micropower import PowerController as pc
p = pc(pin_active_high='Y12', pin_active_low='Y11')
with p:
    f = FRAM(side = 'R')    # Instantiate the hardware under power control
    pyb.mount(f, '/fram')   # Use it
    os.listdir('/fram')
    pyb.mount(None, '/fram')# Perform any tidying up
```

Note that when peripheral is powered up it is usually necessary to create a
device instance as shown above. Typical device drivers use the constructor to
initialise the hardware, so you can't rely on a device instance persisting in a
usable form after a power down event.

The `power_up()` and `power_down()` methods support nested calls, with power
only being removed at the outermost level. Use with care: the SPI and I2C buses
will need to be re-initialised if they are to be used after a `power_down()`
call.

### Footnote: I2C

The Pyboard I2C bus driver doesn't respond well to the following sequence of
events.
 1. Power up the peripheral.
 2. Initialise the bus.
 3. Power down the peripheral.
 4. Repeat the above sequence.

It is necessary to de-initialise the bus prior to re-initialising it. In
principle this could be done in the device constructor. However existing
drivers are unlikely to do this. Consequently the `PowerController` does this
on power down. I don't know of a similar issue with SPI, but the driver
de-initialises this on a precautionary basis.

# Some numbers

The following calculations and measurements are based on a Pyboard 1.1 with
hardware as described above. Similar results can be expected for a D series
with the switchable 3.3V regulator turned on only when required.

The capacity of small batteries is measured in milliamp hours (mAH), a measure
of electric charge. For purposes of measurement on the Pyboard this is rather a
large unit, and milliamp seconds (mAS) or millicoulomb is used here.
1mAH = 3600mAS. Note that, because the Pyboard uses a linear voltage regulator,
the amount of current (and hence charge) used in any situation is substantially
independent of battery voltage.
 
After executing `pyb.standby()` the Pyboard consumes about 6μA. In a year's
running this corrsponds to a charge utilisation of 53mAH, compared to the 225mAH
nominal capacity of a CR2032 cell.
 
@moose measured the startup charge required by the Pyboard 1.x
[here](http://forum.micropython.org/viewtopic.php?f=6&t=607).
This corresponds to about 9mAS or 0.0025mAH. If we start every ten minutes,
annual consumption from startup events is  
0.0025 x 6 x 24 x 365 = 131mAH. Adding the 53mAH from standby gives 184mAH,
close to the capacity of the cell. This sets an upper bound on the frequency of
power up events to achieve the notional one year runtime, although this could
be doubled with an alternative button cell (see below). Two use cases, where
the Pyboard performs a task on waking up, are studied below.

## Use case 1: reading a sensor and transmitting the data

This was tested by reading a BMP180 pressure sensor and transmitting the data
to a base station using an NRF24L01 radio, both with power switched. The
current waveform (red trace, 40mA/div, 100ms/div) is shown below. The yellow
trace shows the switched Vdd supply. Note the 300mA spike in the current
waveform when Vdd switches on: this is caused by the charging of decoupling
capacitors on the attached peripherals.

![Waveform](current.png)

On my estimate the charge used each time the Pyboard wakes from standby is
about 23mAS (comprising some 16mAS to boot up and 7mAS to read and transmit the
data). If this ran once per hour the annual charge use would be  
23 x 24 x 365/3600 mAH = 56mAH  
to which must be added the standby figure of 53mAH. One year's use with a
CR2032 would seem feasible.

The code is listed to indicate the approach used and to clarify my observations
on charge usage. It is incomplete as I have not documented the slave end of the
link or the `radio` module.

```python
import struct, pyb, stm
from radio import TwoWayRadio, RadioSetup
from micropower import PowerController
from bmp180 import BMP180

RadioSetup['ce_pin'] = 'X4'
ledy = pyb.LED(3)

def send_data():
    bmp180 = BMP180('Y')
    pressure = int(bmp180.pressure /100)
    nrf = TwoWayRadio(master = True, **RadioSetup)
    led_state = stm.mem32[stm.RTC + stm.RTC_BKP3R]
    led_state = max(1, (led_state << 1) & 0x0f)
    stm.mem32[stm.RTC + stm.RTC_BKP3R] = led_state
    # stop listening and send packet
    nrf.stop_listening()
    try:
        nrf.send(struct.pack('ii', pressure, led_state))
    except OSError:  # never happens
        pass
    nrf.start_listening()
    # wait for response, with 250ms timeout
    start_time = pyb.millis()
    timeout = False
    while not nrf.any() and not timeout:
        if pyb.elapsed_millis(start_time) > 250:
            timeout = True
    if timeout:
        ledy.on()
        pyb.delay(200) # get to see it before power goes down
        ledy.off()
    else:
        nrf.recv() # discard received data

rtc = pyb.RTC()

usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
if not usb_connected:
    pyb.usb_mode(None) # Save power

if stm.mem32[stm.RTC + stm.RTC_BKP1R] == 0:     # first boot
    rtc.datetime((2020, 8, 6, 4, 13, 0, 0, 0)) # Arbitrary

p = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
with p:
    send_data()
rtc.wakeup(4000)
stm.mem32[stm.RTC + stm.RTC_BKP1R] = 1 # indicate that we are going into standby mode
if usb_connected:
    p.power_up()                        # Power up for testing
else:
    pyb.standby()
```

Measurements were performed with the slave nearby so that timeouts never
occurred. A comparison of the current waveform presented above with that
recorded by @moose shows virtually identical behaviour for the first 180ms as
the Pyboard boots up. There is then a period of some 230ms until power is
applied to the peripherals where the board continues to draw some 60mA:
compilation of imported modules to byte code is likely to be responsible for
the bulk of this charge usage. The code which performs the actual application
- namely power control and the reading and transmission of data is responsible
for about a third of the total charge use.

## Use case 2: Displaying data on an e-paper screen

A more computationally demanding test involved updating an epaper display with
the following script
 
```python
import pyb, epaper, stm
from micropower import PowerController
rtc = pyb.RTC()

usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
if not usb_connected:
    pyb.usb_mode(None) # Save power

if stm.mem32[stm.RTC + stm.RTC_BKP1R] == 0:     # first boot
    rtc.datetime((2015, 8, 6, 4, 13, 0, 0, 0)) # Arbitrary

t = rtc.datetime()[4:7]
timestring = '{:02d}.{:02d}.{:02d}'.format(t[0],t[1],t[2])
p = PowerController(pin_active_high = 'Y12', pin_active_low = 'Y11')
a = epaper.Display(side = 'Y', use_flash = True, pwr_controller = p)
s = str(a.temperature) + "C\n" + timestring
a.mountflash() # Power up
with a.font('/fc/LiberationSerif-Regular45x44'):
    a.puts(s)
a.umountflash() # Keep filesystem happy
a.show()

rtc.wakeup(20000)
stm.mem32[stm.RTC + stm.RTC_BKP1R] = 1 # indicate that we are going into standby mode
if usb_connected:
    p.power_up()                        # Power up for testing
else:
    pyb.standby()
```

Modules epaper and micropower located [here](https://github.com/peterhinch/micropython-epaper.git).

This used an average of 85mA for 6S to do an update. If the script performed
one refresh per hour this would equate to  
85 x 6/3600 = 141μA average + 6μA quiescent = 147μA.__
This would exhaust a CR2032 in 9 weeks. An alternative is the larger CR2450
button cell with 540mAH capacity which would provide 5 months running.

A year's running would be achievable if the circuit were powered from three AA
alkaline cells:  
Power = 141μA + 6μA quiescent = 147μA x 24 x 365 = 1.28AH__
This is within the nominal capacity of these cells.

# Hardware

Hardware as used for tests of power switched peripherals.

![Hardware](hardware.JPG)

# Pyboard 1.x: note for hardware designers

When designing a board intended for micropower operation, consider
incorporating a MOSFET to provide a switched 3.3V supply for peripherals.
Pullups can either be powered from this switched supply, or for greater
flexibility driven from a separately controlled MOSFET.
