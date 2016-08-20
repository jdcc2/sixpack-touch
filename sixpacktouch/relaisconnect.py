import wiringpi
from time import sleep

#NOTE to control the GPIO pins tis program needs root privileges
#Setup the IO pins to use WiringPi numbering (run 'gpio readall' to see the numbering differences and pin layout)
wiringpi.wiringPiSetup()

#The GPIO pins 0-3 are connected to relais 1-4
pinLabels = { 'mixer': 0, 'amp': 1, 'relais3': 2, 'relais4': 3}

def setOutput():
    for label, pin in pinLabels.items():
        wiringpi.pinMode(pin, 1) #Mode 1 means OUTPUT

def enableAudioDevices():
    wiringpi.digitalWrite(pinLabels['mixer'], 1)
    sleep(2)
    wiringpi.digitalWrite(pinLabels['amp'], 1)

def disableAudioDevices():
    wiringpi.digitalWrite(pinLabels['amp'], 0)
    sleep(2)
    wiringpi.digitalWrite(pinLabels['mixer'], 0)

def getStateByLabel(label):
    """

    :param label: label for the pin
    :return: 0 for off and 1 for on
    """

    return wiringpi.digitalRead(pinLabels[label])
