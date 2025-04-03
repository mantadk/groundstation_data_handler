import serial
import time

def log_serial_data(serial_port, baud_rate, output_file):
    # Open serial port
    ser = serial.Serial(serial_port, baud_rate, timeout=1)
    
    # Open file for logging
    with open(output_file, 'a') as log_file:
        while True:
            # Read a line from the serial port
            data = ser.readline()
            
            # If there is data, timestamp it and log it
            if data:
                timestamp = int(time.time())
                log_entry = f"pits:{timestamp};{data.decode('utf-8').strip()}\n"
                
                # Print to console
                print(log_entry.strip())
                
                # Log to file
                log_file.write(log_entry)

# Example usage
log_serial_data('/dev/ttyUSB0', 115200, 'serial_log.txt')
