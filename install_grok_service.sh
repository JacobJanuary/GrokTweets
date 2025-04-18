#!/bin/bash

# Script to install the Grok Categories service

# Exit on error
set -e

# Define variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_NAME="grok-categories"
SERVICE_FILE="${SERVICE_NAME}.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_FILE}"
WRAPPER_SCRIPT="${SCRIPT_DIR}/grok_categories_daemon.py"

# Make sure we're running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Make wrapper script executable
chmod +x "$WRAPPER_SCRIPT"

# Create the service file
cat > "$SERVICE_PATH" << EOL
[Unit]
Description=Grok Categories Service
After=network.target mysql.service

[Service]
User=$(whoami)
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${WRAPPER_SCRIPT}
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

# Optional: Set resource limits if needed
# LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd to recognize the new service
systemctl daemon-reload

# Enable and start the service
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Check service status
systemctl status "$SERVICE_NAME"

echo "Installation complete. The service is now running and set to start automatically on boot."
echo "You can check the logs with: journalctl -u $SERVICE_NAME -f"
echo "You can stop the service with: sudo systemctl stop $SERVICE_NAME"
echo "The daemon also logs to: ${SCRIPT_DIR}/grok_categories_daemon.log"