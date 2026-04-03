#!/bin/bash

# Export all env variables for cron
env > /etc/environment
chmod 600 /etc/environment

# Fetch prayer times
python3 /app/get_time_salat.py

# Start cron daemon
cron

# Keep container alive and stream logs
tail -f /var/log/cron.log
