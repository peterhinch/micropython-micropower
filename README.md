# Designing Pyboard systems for low power consumption

The Pyboard can be used to build systems with extremely low power consumption, and it is possible
to build systems capable of running for over a year on standard batteries such as AA cells or even
coin cells. Achieving the lowest possible power consumption where peripheral devices are attached
requires a little additional hardware.

Broadly there are two approaches, depending on the acceptable level of power consumption. If an
idle current in the range of 500uA to 1mA is acceptable, extra hardware may be unneccessary and
code can be largely conventional with ``pyb.stop()`` being employed to reduce power consumption
during periods when the Pyboard is idle.

For the lowest possible power consumption ``pyb.standby()`` must be used, cutting consumption
to around 6uA. With external hardware the peripherals may be turned off ensuring that the
entire system uses only this amount. The drawback of ``standby`` is that on waking the Pyboard
restarts as if from a reboot. This introduces potential difficulties regarding determining
the source of the wakeup and the storage of program state while sleeping.

Two sets of resources are provided to assist with the development of low power solutions.

### Hardware

[hardware](./HARDWARE.md) A discussion of techniques to minimise power consumption including ways
to shut down attached devices, calculation of battery usage and measurements of results. A
schematic for a typical system is provided with accompanying PCB layout. 

### Software

[upower](./UPOWER.md) This documents ``upower.py``, a module providing access to features of the
Pyboard SOC which are currently unsupported in the official firmware. Some of these features may
be of wider use, such as using the battery backed RAM to store arbitrary Python objects and
accessing the RTC registers.

Solutions are based on Pyboard hardware V1.0 or V1.1.

All code is issued under the [MIT license](./LICENSE)
