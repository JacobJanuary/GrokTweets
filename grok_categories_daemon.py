#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import logging
from datetime import datetime

# Setup logging
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'grok_categories_daemon.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Path to the main script
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grok_categories.py')

# Check interval in seconds (e.g., 5 minutes = 300 seconds)
CHECK_INTERVAL = 300


def run_script():
    """
    Run the grok_categories.py script and log the output
    """
    try:
        logging.info(f"Starting grok_categories.py at {datetime.now()}")

        # Run the script and capture its output
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            capture_output=True,
            text=True
        )

        # Log stdout
        for line in result.stdout.splitlines():
            logging.info(f"SCRIPT: {line}")

        # Log stderr if there was any error
        if result.stderr:
            for line in result.stderr.splitlines():
                logging.error(f"SCRIPT ERROR: {line}")

        logging.info(f"Finished grok_categories.py run at {datetime.now()}")

        # Return True if the script ran successfully
        return result.returncode == 0

    except Exception as e:
        logging.error(f"Error running script: {e}")
        return False


def main():
    """
    Main loop to continuously run the script at intervals
    """
    logging.info(f"Starting grok_categories daemon. Will check every {CHECK_INTERVAL} seconds")

    while True:
        # Run the script
        success = run_script()

        if not success:
            logging.warning("Script run failed, will retry after interval")

        # Sleep until the next check
        logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Daemon stopped by user")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}")
        raise