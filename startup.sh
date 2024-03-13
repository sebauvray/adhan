#!/bin/bash

python3 /app/get_time_salat.py

cron 

sleep 5

tail -f /var/log/cron.log
