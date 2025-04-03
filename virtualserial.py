import time
import RPi.GPIO as GPIO

VIRTUAL_NOTIFY_LINE = 1
VIRTUAL_ENABLE_LINE = 7
VIRTUAL_DATA_LINE = 25
VIRTUAL_CLOCK_LINE = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(VIRTUAL_NOTIFY_LINE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(VIRTUAL_ENABLE_LINE, GPIO.OUT)
GPIO.setup(VIRTUAL_DATA_LINE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(VIRTUAL_CLOCK_LINE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def wait_for_notif():
    while GPIO.input(VIRTUAL_NOTIFY_LINE) == GPIO.LOW:
        pass
def enable():
    GPIO.output(VIRTUAL_ENABLE_LINE, GPIO.HIGH)

def disable():
    GPIO.output(VIRTUAL_ENABLE_LINE, GPIO.LOW)

def read():
    return GPIO.input(VIRTUAL_DATA_LINE) == GPIO.HIGH

def wait_for_clock_high():
    while GPIO.input(VIRTUAL_CLOCK_LINE) == GPIO.LOW:
        pass

def wait_for_clock_low():
    while GPIO.input(VIRTUAL_CLOCK_LINE) == GPIO.HIGH:
        pass



def bool_arr_to_char(bits):
    c = 0
    for i in range(8):
        c |= bits[i] << i
    return chr(c)

def read_char():
    bits = []
    for _ in range(8):
        enable()
        wait_for_clock_high()
        bits.append(read())
        disable()
        wait_for_clock_low()
    return bool_arr_to_char(bits)

def read_vuart_string():
    received_data = ""
    wait_for_notif()
    while True:
        c = read_char()
        if c == '\n':
            break
        received_data += c
    return received_data

def print_received():
    received_message = read_vuart_string()
    print("Received:", received_message)

def main():
    try:
        print("Waiting for virtual UART data...")
        while True:
            print_received()
    finally:
        print("Finished")

if __name__ == "__main__":
    main()
