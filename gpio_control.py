import RPi.GPIO as GPIO

def setup_gpio(pin):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def control_heater(pin, pid_output):
    if pid_output > 50:
        GPIO.output(pin, GPIO.HIGH)  # Turn on the heater
    else:
        GPIO.output(pin, GPIO.LOW)  # Turn off the heater
