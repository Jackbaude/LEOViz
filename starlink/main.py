# flake8: noqa: E501
import time
import logging
import argparse
import schedule
import threading

import config
from latency import icmp_ping
from dish import (
    grpc_get_status,
    get_sinr,
    get_obstruction_map,
)
from util import run, load_tle
from config import print_config
from gps_reader import GPSReader


logger = logging.getLogger(__name__)


schedule.every(1).hours.at(":00").do(run, icmp_ping).tag("Latency")
schedule.every(1).hours.at(":00").do(run, grpc_get_status).tag("gRPC")
schedule.every(1).hours.at(":00").do(run, get_obstruction_map).tag("gRPC")
schedule.every(1).hours.at(":00").do(run, get_sinr).tag("gRPC")
schedule.every(1).hours.at(":00").do(run, load_tle).tag("TLE")


def update_gps_config(gps_data):
    """Update config with latest GPS data"""
    if gps_data['status'] == 'A':  # Only update if GPS fix is valid
        config.LATITUDE = gps_data['latitude']
        config.LONGITUDE = gps_data['longitude']
        # Note: We don't have altitude from GPS, so we keep the configured value
        logger.debug(f"Updated position: {config.LATITUDE}, {config.LONGITUDE}")

def run_gps_stream():
    """Run GPS stream in a separate thread"""
    with GPSReader() as gps:
        for data in gps.stream():
            update_gps_config(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LEOViz | Starlink metrics collection")

    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    parser.add_argument("--lat", type=float, required=False, help="Dish latitude")
    parser.add_argument("--lon", type=float, required=False, help="Dish longitude")
    parser.add_argument("--alt", type=float, required=False, help="Dish altitude")
    parser.add_argument("--mobile", type=bool, required=False, help="Mobile mode")
    args = parser.parse_args()

    print_config()
    if args.mobile:
        config.MOBILE = args.mobile
        
    if args.lat and args.lon and args.alt:
        config.LATITUDE = args.lat
        config.LONGITUDE = args.lon
        config.ALTITUDE = args.alt
    else:
        logger.warning(
            "Latitude, Longitude and Altitude not provided. Won't estimate connected satellites."
        )

    if args.run_once:
        schedule.run_all()
    else:
        # Start GPS stream in a separate thread
        gps_thread = threading.Thread(target=run_gps_stream, daemon=True)
        gps_thread.start()

        # Log scheduled jobs
        for job in schedule.get_jobs("Latency"):
            logger.info("[Latency]: {}".format(job.next_run))
        for job in schedule.get_jobs("TLE"):
            logger.info("[TLE]: {}".format(job.next_run))
        for job in schedule.get_jobs("gRPC"):
            logger.info("[gRPC]: {}".format(job.next_run))

        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
