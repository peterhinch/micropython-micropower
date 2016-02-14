# upower.py Enables access to functions useful in low power Pyboard projects
# Copyright 2015 Peter Hinch
# This code is released under the MIT licence

# V0.3 13th February 2016

# http://www.st.com/web/en/resource/technical/document/application_note/DM00025071.pdf
import pyb, stm, os, utime, uctypes

# CODE RUNS ON IMPORT **** START ****

def buildcheck(tupTarget):
    fail = True
    if 'uname' in dir(os):
        datestring = os.uname()[3]
        date = datestring.split(' on')[1]
        idate = tuple([int(x) for x in date.split('-')])
        fail = idate < tupTarget
    if fail:
        raise OSError('This driver requires a firmware build dated {:4d}-{:02d}-{:02d} or later'.format(*tupTarget))

buildcheck((2016, 02, 11))                      # Version allows 32 bit write to stm register

usb_connected = False
if pyb.usb_mode() is not None:                  # User has enabled CDC in boot.py
    usb_connected = pyb.Pin.board.USB_VBUS.value() == 1
    if not usb_connected:
        pyb.usb_mode(None)                      # Save power

# CODE RUNS ON IMPORT **** END ****

def bounds(val, minval, maxval, msg):           # Bounds check
    if not (val >= minval and val <= maxval):
        raise ValueError(msg)

def singleton(cls):
    instances = {}
    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return getinstance

class RTCError(OSError):
    pass

def cprint(*args, **kwargs):                    # Conditional print: USB fails if low power modes are used
    global usb_connected
    if not usb_connected:                       # assume a UART has been specified in boot.py
        print(*args, **kwargs)

@micropython.asm_thumb
def ctz(r0):                                    # Count the trailing zeros in an integer
    rbit(r0, r0)
    clz(r0, r0)

# ***** BACKUP RAM SUPPORT *****

@singleton
class BkpRAM(object):
    BKPSRAM = 0x40024000
    def __init__(self):
        stm.mem32[stm.RCC + stm.RCC_APB1ENR] |= 0x10000000 # PWREN bit
        stm.mem32[stm.PWR + stm.PWR_CR] |= 0x100  # Set the DBP bit in the PWR power control register
        stm.mem32[stm.RCC +stm.RCC_AHB1ENR]|= 0x40000 # enable BKPSRAMEN
        stm.mem32[stm.PWR + stm.PWR_CSR] |= 0x200 # BRE backup register enable bit
        self._ba = uctypes.bytearray_at(self.BKPSRAM, 4096)
    def idxcheck(self, idx):
        bounds(idx, 0, 0x3ff, 'RTC backup RAM index out of range')
    def __getitem__(self, idx):
        self.idxcheck(idx)
        return stm.mem32[self.BKPSRAM + idx * 4]
    def __setitem__(self, idx, val):
        self.idxcheck(idx)
        stm.mem32[self.BKPSRAM + idx * 4] = val
    @property
    def ba(self):
        return self._ba                         # Access as bytearray

# ***** RTC REGISTERS *****

@singleton
class RTCRegs(object):
    def idxcheck(self, idx):
        bounds(idx, 0, 19, 'RTC register index out of range')
    def __getitem__(self, idx):
        self.idxcheck(idx)
        return stm.mem32[stm.RTC + stm.RTC_BKP0R+ idx * 4]
    def __setitem__(self, idx, val):
        self.idxcheck(idx)
        stm.mem32[stm.RTC + stm.RTC_BKP0R + idx * 4] = val


# ***** LOW POWER pyb.delay() ALTERNATIVE *****
def lpdelay(ms):                                # Low power delay. Note stop() kills USB
    global usb_connected
    rtc = pyb.RTC()
    if usb_connected:
        pyb.delay(ms)
        return
    rtc.wakeup(ms)
    pyb.stop()
    rtc.wakeup(None)

# ***** TAMPER (X18) PIN SUPPORT *****

@singleton
class Tamper(object):
    def __init__(self):
        self.edge_triggered = False
        self.triggerlevel = 0
        self.tampmask = 0
        self.disable()                          # Ensure no events occur until we're ready
        self.pin = pyb.Pin.board.X18
        self.pin_configured = False             # Conserve power: enable pullup only if needed
        self.setup()

    def setup(self, level = 0, *, freq = 16, samples = 2, edge = False):
        self.tampmask = 0
        if level == 1:
            self.tampmask |= 2
            self.triggerlevel = 1
        elif level == 0:
            self.triggerlevel = 0
        else:
            raise ValueError("level must be 0 or 1")
        if type(edge) == bool:
            self.edge_triggered = edge
        else:
            raise ValueError("edge must be True or False")
        if not self.edge_triggered:
            if freq in (1,2,4,8,16,32,64,128):
                self.tampmask |= ctz(freq) << 8
            else:
                raise ValueError("Frequency must be 1, 2, 4, 8, 16, 32, 64 or 128Hz")
            if samples in (2, 4, 8):
                self.tampmask |= ctz(samples) << 11
            else:
                raise ValueError("Number of samples must be 2, 4, or 8")

    def _pinconfig(self):
        if not self.pin_configured:
            self.pin.init(mode = pyb.Pin.IN, pull = pyb.Pin.PULL_UP)
            self.pin_configured = True

    def disable(self):
        stm.mem32[stm.RTC + stm.RTC_TAFCR] = self.tampmask

    def wait_inactive(self):
        self._pinconfig()
        while self.pin.value() == self.triggerlevel: # Wait for pin to go logically off
            lpdelay(50)

    @property
    def pinvalue(self):
        self._pinconfig()
        return self.pin.value()

    def enable(self):
        BIT21 = 1 << 21                                 # Tamper mask bit
        self.disable()
        stm.mem32[stm.EXTI + stm.EXTI_IMR] |= BIT21     # Set up ext interrupt
        stm.mem32[stm.EXTI + stm.EXTI_RTSR] |= BIT21    # Rising edge
        stm.mem32[stm.EXTI + stm.EXTI_PR] |= BIT21      # Clear pending bit

        stm.mem32[stm.RTC + stm.RTC_ISR] &= 0xdfff      # Clear tamp1f flag
        stm.mem32[stm.PWR + stm.PWR_CR] |= 4            # Clear power wakeup flag WUF
        stm.mem32[stm.RTC + stm.RTC_TAFCR] = self.tampmask | 5 # Tamper interrupt enable and tamper1 enable

# ***** WKUP PIN (X1) SUPPORT *****

@singleton
class wakeup_X1(object):                                # Support wakeup on low-high edge on pin X1
    def __init__(self):
        self.disable()
        self.pin = pyb.Pin.board.X1                     # Don't configure pin unless user accesses wkup
        self.pin_configured = False

    def _pinconfig(self):
        if not self.pin_configured:
            self.pin.init(mode = pyb.Pin.IN, pull = pyb.Pin.PULL_DOWN)
            self.pin_configured = True

    def enable(self):                                   # In this mode pin has pulldown enabled
        stm.mem32[stm.PWR + stm.PWR_CR] |= 4            # set CWUF to clear WUF in PWR_CSR
        stm.mem32[stm.PWR + stm.PWR_CSR] |= 0x100       # Enable wakeup

    def disable(self):
        stm.mem32[stm.PWR + stm.PWR_CSR] &= 0xfffffeff  # Disable wakeup

    def wait_inactive(self):
        self._pinconfig()
        while self.pin.value() == 1:                    # Wait for pin to go low
            lpdelay(50)

    @property
    def pinvalue(self):
        self._pinconfig()
        return self.pin.value()

# ***** RTC TIMER SUPPORT *****

def bcd(x): # integer to BCD (2 digit max)
    return (x % 10) + ((x//10) << 4)

class Alarm(object):
    instantiated = False
    def __init__(self, ident):
        if not ident in ('a','A','b','B'):
            raise ValueError("Alarm iIdent must be 'A' or 'B'")
        self.ident = ident.lower()
        if self.ident == 'a':
            self.alclear = 0xffeeff
            self.alenable = 0x1100
            self.alreg = stm.RTC_ALRMAR
            self.alisr = 0x1feff
            self.albit = 1
        else:
            self.alclear = 0xffddff
            self.alenable = 0x2200
            self.alreg = stm.RTC_ALRMBR
            self.alisr = 0x1fdff
            self.albit = 2
        self.uval = 0
        self.lval = 0
        if not Alarm.instantiated:
            BIT17 = 1 << 17
            Alarm.instantiated = True
            stm.mem32[stm.EXTI + stm.EXTI_IMR] |= BIT17     # Set up ext interrupt
            stm.mem32[stm.EXTI + stm.EXTI_RTSR] |= BIT17    # Rising edge
            stm.mem32[stm.EXTI + stm.EXTI_PR] |= BIT17      # Clear pending bit

    def timeset(self, *, day_of_month = None, weekday = None, hour = None, minute = None, second = None):
        self.uval = 0x8080                      # Mask everything off
        self.lval = 0x8080
        setlower = False
        if day_of_month is not None:
            bounds(day_of_month, 1 , 31, "Day of month must be between 1 and 31")
            self.uval &= 0x7fff                # Unmask day
            self.uval |= (bcd(day_of_month) << 8)
            setlower = True
        elif weekday is not None:
            bounds(weekday, 1, 7, "Weekday must be from 1 (Monday) to 7")
            self.uval &= 0x7fff                 # Unmask day
            self.uval |= 0x4000                 # Indicate day of week
            self.uval |= (weekday << 8)
            setlower = True
        if hour is not None:
            bounds(hour, 0, 23, "Hour must be 0 to 23")
            self.uval &= 0xff3f                 # Unmask hour, force 24 hour format
            self.uval |= bcd(hour)
            setlower = True
        elif setlower:
            self.uval &= 0xff3f                 # Unmask hour, force 24 hour format
        if minute is not None:
            bounds(minute, 0, 59, "Minute must be 0 to 59")
            self.lval &= 0x7fff                 # Unmask minute
            self.lval |= (bcd(minute) << 8)
            setlower = True
        elif setlower:
            self.lval &= 0x7fff                 # Unmask minute
        if second is not None:
            bounds(second, 0, 59, "Second must be 0 to 59")
            self.lval &= 0xff7f                 # Unmask second
            self.lval |= bcd(second)
        elif setlower:
            self.lval &= 0xff7f                 # Unmask second
        stm.mem32[stm.RTC + stm.RTC_WPR] |= 0xCA            # enable write
        stm.mem32[stm.RTC + stm.RTC_WPR] |= 0x53
        stm.mem32[stm.RTC + stm.RTC_CR] &= self.alclear     # Clear ALRxE in RTC_CR to disable Alarm 
        if self.uval == 0x8080 and self.lval == 0x8080:     # No alarm set: disable
            stm.mem32[stm.RTC + stm.RTC_WPR] = 0xff         # Write protect
            return
        pyb.delay(5)
        if stm.mem32[stm.RTC + stm.RTC_ISR] & self.albit :  # test ALRxWF IN RTC_ISR
            stm.mem32[stm.RTC + self.alreg] = self.lval + (self.uval << 16)
            stm.mem32[stm.RTC + stm.RTC_ISR] &= self.alisr  # Clear the RTC alarm ALRxF flag
            stm.mem32[stm.PWR + stm.PWR_CR] |= 4            # Clear the PWR Wakeup (WUF) flag
            stm.mem32[stm.RTC+stm.RTC_CR] |= self.alenable  # Enable the RTC alarm and interrupt
            stm.mem32[stm.RTC + stm.RTC_WPR] = 0xff
        else:
            raise OSError("Can't access alarm " + self.ident)

# Return the reason for a wakeup event. Note that boot detection uses the last word of backup RAM.
def why():
    result = None
    bkpram = BkpRAM()
    if stm.mem32[stm.PWR+stm.PWR_CSR] & 2 == 0:
        if bkpram[1023] != 0x27288a6f:
            result = 'BOOT'
            bkpram[1023] = 0x27288a6f                       # In case a backup battery is in place
        else:
            result = 'POWERUP'                              # a backup battery is in place
    else:
        rtc_isr = stm.mem32[stm.RTC + stm.RTC_ISR]
        if rtc_isr & 0x2000:
            result = 'TAMPER'
        elif rtc_isr & 0x400:
            result = 'WAKEUP'
        elif rtc_isr & 0x200:
            stm.mem32[stm.RTC + stm.RTC_ISR] |= 0x200
            result = 'ALARM_B'
        elif rtc_isr & 0x100 :
            stm.mem32[stm.RTC + stm.RTC_ISR] |= 0x100
            result = 'ALARM_A'
        elif stm.mem32[stm.PWR + stm.PWR_CSR] & 1:          # WUF set: the only remaining cause is X1 (?)
            result = 'X1'                                   # if WUF not set, cause unknown, return None
    stm.mem32[stm.PWR + stm.PWR_CR] |= 4                    # Clear the PWR Wakeup (WUF) flag
    return result

def now():  # Return the current time from the RTC in millisecs from year 2000
    rtc = pyb.RTC()
    secs = utime.time()
    ms = 1000*(255 -rtc.datetime()[7]) >> 8
    if ms < 50:                                 # Might have just rolled over
        secs = utime.time()
    return ms + 1000 * secs

def lp_elapsed_ms(tstart):                      # An elapsed_ms function which works during lpdelays
    return now() - tstart

# Save the current time in mS 
def savetime(addr = 1021):
    bkpram = BkpRAM()
    bkpram[addr], bkpram[addr +1] = divmod(now(), 1000)

# Return the number of mS outstanding from a delay of delta mS
def ms_left(delta, addr = 1021):
    bkpram = BkpRAM()
    if not (bkpram[addr +1] <= 1000 and bkpram[addr +1] >= 0):
        raise RTCError("Time data not saved.")
    start_ms = 1000 * bkpram[addr] + bkpram[addr +1]
    now_ms = now()
    result = max(start_ms + delta - now_ms, 0)  # avoid -ve results where time was missed (e.g. power outage)
    if result > delta:
        raise RTCError("Invalid saved time data.")
    return result

def adcread(chan):                              # 16 temp 17 vbat 18 vref
    bounds(chan, 16, 18, 'Invalid ADC channel')
    start = pyb.millis()
    timeout = 100
    stm.mem32[stm.RCC + stm.RCC_APB2ENR] |= 0x100 # enable ADC1 clock.0x4100
    stm.mem32[stm.ADC1 + stm.ADC_CR2] = 1       # Turn on ADC
    stm.mem32[stm.ADC1 + stm.ADC_CR1] = 0       # 12 bit
    if chan == 17:
        stm.mem32[stm.ADC1 + stm.ADC_SMPR1] = 0x200000 # 15 cycles channel 17
        stm.mem32[stm.ADC + 4] = 1 << 23
    elif chan == 18:
        stm.mem32[stm.ADC1 + stm.ADC_SMPR1] = 0x1000000 # 15 cycles channel 18 0x1200000
        stm.mem32[stm.ADC + 4] = 0xc00000
    else:
        stm.mem32[stm.ADC1 + stm.ADC_SMPR1] = 0x40000 # 15 cycles channel 16
        stm.mem32[stm.ADC + 4] = 1 << 23
    stm.mem32[stm.ADC1 + stm.ADC_SQR3] = chan
    stm.mem32[stm.ADC1 + stm.ADC_CR2] = 1 | (1 << 30) | (1 << 10) # start conversion
    while not stm.mem32[stm.ADC1 + stm.ADC_SR] & 2: # wait for EOC
        if pyb.elapsed_millis(start) > timeout:
            raise OSError('ADC timout')
    data = stm.mem32[stm.ADC1 + stm.ADC_DR]     # clears down EOC
    stm.mem32[stm.ADC1 + stm.ADC_CR2] = 0       # Turn off ADC
    return data

def v33():
    return 4096 * 1.21 / adcread(17)

def vbat():
    return  1.21 * 2 * adcread(18) / adcread(17)  # 2:1 divider on Vbat channel

def vref():
    return 3.3 * adcread(17) / 4096

def temperature():
    return 25 + 400 * (3.3 * adcread(16) / 4096 - 0.76)

# ********** OLD API AND TEST CODE **********
def battery_volts():
    adc = pyb.ADCAll(12)
    return adc.read_core_vbat(), 3.3/(adc.read_core_vref()/1.21)

def ms_set(): # For debug purposes only. Decodes outcome of setting rtc.wakeup().
    dividers = (16, 8, 4, 2)
    wucksel = stm.mem32[stm.RTC + stm.RTC_CR] & 7
    div = dividers[wucksel & 3]
    wut = stm.mem32[stm.RTC + stm.RTC_WUTR] & 0xffff
    clock_period = div/32768 if wucksel < 4 else 1.0  # seconds
    period = clock_period * wut if wucksel < 6 else clock_period * (wut + 0x10000)
    return 1000 * period
