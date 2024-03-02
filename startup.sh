#!/bin/bash

python3 /app/get_time_salat.py

cron

tail -f /var/log/cron.log
