import socket
import sys
import time
from datetime import datetime
from typing import Callable, Optional, Generator, Dict, Any

# ANSI color codes
GREEN = '\033[1;32m'
RED = '\033[1;31m'
WHITE = '\033[1;37m'
RESET = '\033[0m'

class GPSReader:
    def __init__(self, host: str = "10.0.0.30", port: int = 11123):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.message_count = 0
        self.start_time = 0
        self.last_message_time = 0

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Error connecting to GPS: {str(e)}")
            return False

    def parse_nmea_rmc(self, nmea_string: str) -> Optional[Dict[str, Any]]:
        """Parse GPRMC NMEA sentence"""
        if not nmea_string.startswith('$GPRMC'):
            return None
            
        try:
            fields = nmea_string.split(',')
            time_str = fields[1]
            status = fields[2]
            lat = fields[3]
            lat_dir = fields[4]
            lon = fields[5]
            lon_dir = fields[6]
            speed = fields[7]
            course = fields[8]
            date_str = fields[9]
            
            # Convert latitude
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:])
            lat_dec = lat_deg + (lat_min / 60.0)
            if lat_dir == 'S':
                lat_dec = -lat_dec
                
            # Convert longitude
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:])
            lon_dec = lon_deg + (lon_min / 60.0)
            if lon_dir == 'W':
                lon_dec = -lon_dec
                
            # Convert speed from knots to km/h
            speed_kmh = float(speed) * 1.852
            
            # Parse date and time
            date_time = datetime.strptime(f"{date_str}{time_str}", "%d%m%y%H%M%S.%f")
            
            return {
                'time': date_time,
                'latitude': lat_dec,
                'longitude': lon_dec,
                'speed': speed_kmh,
                'course': float(course),
                'status': status
            }
        except Exception:
            return None

    def get_gps_data(self) -> Optional[Dict[str, Any]]:
        try:
            data = self.sock.recv(4096)
            nmea_string = data.decode('utf-8').strip()
            return self.parse_nmea_rmc(nmea_string)
        except Exception:
            return None

    def stream(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Generator[Dict[str, Any], None, None]:
        """Stream GPS data either to a callback or as a generator"""
        if not self.sock and not self.connect():
            raise ConnectionError("Failed to connect to GPS device")

        self.running = True
        self.message_count = 0
        self.start_time = time.time()
        self.last_message_time = self.start_time

        try:
            while self.running:
                gps_data = self.get_gps_data()
                if gps_data:
                    current_time = time.time()
                    self.message_count += 1
                    elapsed_time = current_time - self.start_time
                    message_rate = self.message_count / elapsed_time
                    time_since_last = current_time - self.last_message_time
                    self.last_message_time = current_time

                    # Add timing info to the data
                    gps_data.update({
                        'message_rate': message_rate,
                        'time_since_last': time_since_last,
                        'message_count': self.message_count
                    })

                    if callback:
                        callback(gps_data)
                    yield gps_data

                time.sleep(0.001)

        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            self.stop()
            raise e

    def stop(self):
        """Stop the GPS stream"""
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# Example usage:
if __name__ == "__main__":
    def print_gps_data(data):
        print(f"\rTime: {data['time']} | "
              f"Lat: {data['latitude']:.6f}° | "
              f"Lon: {data['longitude']:.6f}° | "
              f"Speed: {data['speed']:.1f} km/h | "
              f"Rate: {data['message_rate']:.1f} Hz", end='')

    with GPSReader() as gps:
        try:
            for data in gps.stream(print_gps_data):
                pass
        except KeyboardInterrupt:
            print("\nStopping GPS stream...")