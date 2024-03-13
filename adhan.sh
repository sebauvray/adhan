#!/bin/bash

python3 /app/home_assistant.py --action "turn_on"
sleep 60
python3 /app/home_assistant.py --action "turn_off"