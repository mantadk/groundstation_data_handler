import serial
import serial.tools.list_ports
import datetime
import sys
import time
import json
import re
import os # Needed for checking file existence

# --- Configuration ---
BAUD_RATE = 115200  # Set your desired baud rate here
SENSOR_LOG_FILE = "sensorlog.json"
GPS_LOG_FILE = "gpslog.json"
# --- End Configuration ---

# --- Regular Expressions for Parsing ---
# Matches the overall line structure, capturing the data inside quotes, optional rssi, optional length
# Example: [timestamp] packet: "DATA_STRING", rssi: -4, length: 128
# Groups: 1=DATA_STRING, 2=RSSI_VALUE(optional), 3=LENGTH_VALUE(optional)
LINE_REGEX = re.compile(r'packet:\s*\"(.*?)\"(?:,\s*rssi:\s*(-?\d+))?(?:,\s*length:\s*(\d+))?')

# Matches the packet ID and the rest of the data string
# Example: "0.06 - t1:24.70C;..." or "0.05 - gps:msg:..."
# Groups: 1=PACKET_ID, 2=REST_OF_DATA
DATA_SPLIT_REGEX = re.compile(r'^\s*([\d\.]+)\s*-\s*(.*)$')

# --- Helper Functions ---

def list_serial_ports():
    """ Lists serial port names compatible with Windows"""
    # (Code identical to the previous version - keeping it for completeness)
    if not sys.platform.startswith('win'):
        print("Warning: This script is primarily designed for Windows COM ports.")
        ports = serial.tools.list_ports.comports()
    else:
        ports = serial.tools.list_ports.comports()

    available_ports = []
    print("Available serial ports:")
    if not ports:
        print("  <No serial ports found>")
        return available_ports

    for i, port_info in enumerate(ports):
        print(f"  {i}: {port_info.device} ({port_info.description})")
        available_ports.append(port_info.device)
    return available_ports

def parse_sensor_data(packet_id, data_content, rssi, length, timestamp):
    """Parses the sensor data string and returns a dictionary."""
    data_dict = {}
    parts = data_content.split(';')
    for part in parts:
        if ':' in part:
            key, value_str = part.split(':', 1)
            key = key.strip()
            value_str = value_str.strip()
            # Remove common units and convert to float
            cleaned_value_str = re.sub(r'(?:C|hPa|%)$', '', value_str)
            try:
                data_dict[key] = float(cleaned_value_str)
            except ValueError:
                # Keep as string if conversion fails
                data_dict[key] = value_str
        # else: handle parts without ':' if needed

    json_output = {
        "timestamp": timestamp,
        "packet_id": packet_id,
        "type": "sensor",
        "data": data_dict
    }
    if rssi is not None:
        try:
            json_output["rssi"] = int(rssi)
        except ValueError:
            pass # ignore if rssi is not a valid int
    if length is not None:
        try:
            json_output["length"] = int(length)
        except ValueError:
            pass # ignore if length is not a valid int

    return json_output

def parse_gps_data(packet_id, data_content, timestamp):
    """Parses the GPS data string and returns a dictionary."""
    gps_msg = data_content.replace('gps:', '', 1).strip()
    json_output = {
        "timestamp": timestamp,
        "packet_id": packet_id,
        "type": "gps",
        "gps_message": gps_msg
    }
    # GPS format doesn't seem to include rssi/length based on example
    return json_output

def load_json_data(filename):
    """Loads data from a JSON file, returns a list or empty list if error/not found."""
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                return []
            data = json.loads(content)
            # Ensure it's a list
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load or parse {filename}. Starting fresh. Error: {e}")
        # Optionally backup the corrupted file here
        return []

def save_json_data(filename, data_list):
    """Saves a list of data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4) # Use indent for readability
        print(f"Data successfully saved to {filename}")
    except IOError as e:
        print(f"Error: Could not write to {filename}. Error: {e}")
    except TypeError as e:
        print(f"Error: Could not serialize data to JSON for {filename}. Error: {e}")


# --- Main Execution ---

def main():
    """Main function to select port, connect, read, parse, and log to JSON."""
    print("--- Serial JSON Logger ---")

    available_ports = list_serial_ports()
    if not available_ports:
        print("\nNo serial ports detected. Please ensure your device is connected.")
        sys.exit(1)

    # --- Port Selection ---
    selected_port = None
    while selected_port is None:
        try:
            choice = input("Enter the number of the port you want to use: ")
            port_index = int(choice)
            if 0 <= port_index < len(available_ports):
                selected_port = available_ports[port_index]
            else:
                print("Invalid choice. Please enter a number from the list.")
        except (ValueError, IndexError):
             print("Invalid input. Please enter a number from the list.")

    print(f"\nSelected port: {selected_port}")
    print(f"Using baud rate: {BAUD_RATE}")
    print(f"Logging sensor data to: {SENSOR_LOG_FILE}")
    print(f"Logging GPS data to: {GPS_LOG_FILE}")
    print("--------------------------")
    print("Loading existing log data...")

    # Load existing data
    sensor_data_list = load_json_data(SENSOR_LOG_FILE)
    gps_data_list = load_json_data(GPS_LOG_FILE)
    print(f"Loaded {len(sensor_data_list)} sensor records and {len(gps_data_list)} GPS records.")

    print("Attempting to open port...")
    print("Press Ctrl+C to stop logging and save data.")

    # --- Serial Connection and Logging ---
    ser = None
    try:
        ser = serial.Serial(selected_port, BAUD_RATE, timeout=1)
        print(f"Successfully opened {selected_port}. Waiting for data...")

        while True:
            try:
                if ser.in_waiting > 0:
                    line_bytes = ser.readline()
                    try:
                        line_str = line_bytes.decode('utf-8', errors='replace').strip()
                        print(line_str)
                    except UnicodeDecodeError:
                        print(f"Warning: Could not decode bytes: {line_bytes!r}")
                        continue # Skip this line

                    if not line_str:
                        continue

                    # --- Parsing Logic ---
                    line_match = LINE_REGEX.search(line_str)
                    if not line_match:
                        # print(f"Debug: Line did not match main structure: {line_str}")
                        continue # Skip lines not matching the expected "packet: ..." format

                    data_string = line_match.group(1)
                    rssi = line_match.group(2) # Will be None if not present
                    length = line_match.group(3) # Will be None if not present

                    data_split_match = DATA_SPLIT_REGEX.match(data_string)
                    if not data_split_match:
                        print(f"Debug: Data string part did not match ID split: {data_string}")
                        continue # Skip if format "ID - data" is not found

                    packet_id = data_split_match.group(1)
                    data_content = data_split_match.group(2)

                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    parsed_json = None

                    # Decide between Sensor and GPS based on content
                    if 'gps:' in data_content:
                        parsed_json = parse_gps_data(packet_id, data_content, timestamp)
                        if parsed_json:
                           gps_data_list.append(parsed_json)
                           print(f"GPS Logged: {packet_id}")
                    # Check for sensor keys (add more if needed)
                    elif any(key + ':' in data_content for key in ['t1', 't2', 'p', 'h', 'ax', 'ay', 'az', 'gx', 'gy', 'gz']):
                        parsed_json = parse_sensor_data(packet_id, data_content, rssi, length, timestamp)
                        if parsed_json:
                            sensor_data_list.append(parsed_json)
                            print(f"Sensor Logged: {packet_id}, RSSI: {rssi}, Len: {length}")
                    else:
                        print(f"Debug: Unrecognized data content format: {data_content}")
                        pass # Ignore unrecognized formats for now

                    # Optional: Print the parsed JSON to console
                    # if parsed_json:
                    #    print(json.dumps(parsed_json, indent=2))

                time.sleep(0.01) # Prevent high CPU usage

            except serial.SerialException as e:
                print(f"\n--- Serial Error: {e} ---")
                print("Port might have been disconnected. Attempting to reconnect...")
                if ser and ser.is_open:
                    ser.close()
                time.sleep(5)
                try:
                    ser.open()
                    print("--- Reconnected successfully. Resuming log. ---")
                except serial.SerialException:
                    print("--- Reconnect failed. Stopping log. ---")
                    break # Exit the inner loop on failed reconnect

    except serial.SerialException as e:
        print(f"\nError: Could not open serial port {selected_port}.")
        print(f"Details: {e}")
    except KeyboardInterrupt:
        print("\n--- Logging stopped by user (Ctrl+C) ---")
    except Exception as e:
        print(f"\n--- An unexpected error occurred: {e} ---")
    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"Serial port {selected_port} closed.")

        # Save data on exit
        print("\nSaving data to JSON files...")
        save_json_data(SENSOR_LOG_FILE, sensor_data_list)
        save_json_data(GPS_LOG_FILE, gps_data_list)
        print("Exiting script.")

if __name__ == "__main__":
    main()