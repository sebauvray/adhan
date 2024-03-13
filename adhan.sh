#!/bin/bash

# Lancement de l'adhan
echo "Lancement de l'adhan a $(date '+ %H:%M:%S %d-%m-%Y')"
python3 /app/home_assistant.py --action "turn_on"

sleep 60

# Reset bouton pour adhan
echo "Réinitialisation du bouton homekit a $(date '+ %H:%M:%S %d-%m-%Y')"
python3 /app/home_assistant.py --action "turn_off"