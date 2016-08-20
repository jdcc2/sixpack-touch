import wiringpi
from time import sleep

#NOTE to control the GPIO pins tis program needs root privileges
#Setup the IO pins to use WiringPi numbering (run 'gpio readall' to see the numbering differences and pin layout)
wiringpi.wiringPiSetup()

#The GPIO pins 0-3 are connected to relais 1-4
pinLabels = { 'relais1': 0, 'relais2': 1, 'relais3': 2, 'relais4': 3}

def setOutput():
    for label, pin in pinLabels.items():
        wiringpi.pinMode(pin, 1) #Mode 1 means OUTPUT

def enableOneTwoTimed():
    wiringpi.digitalWrite(pinLabels['relais1'], 1)
    sleep(2)
    wiringpi.digitalWrite(pinLabels['relais2'], 1)

def disableOneTwoTimed():
    wiringpi.digitalWrite(pinLabels['relais2'], 0)
    sleep(2)
    wiringpi.digitalWrite(pinLabels['relais1'], 0)


