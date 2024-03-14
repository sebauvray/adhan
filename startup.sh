#!/bin/bash

#Export all env variable
env > /etc/environment

python3 /app/get_time_salat.py &

cron -f &

sleep 5

tail -f /var/log/cron.log >&1
