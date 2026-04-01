import requests
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import get_value


def call_home_assistant(service, token, base_url, entity_id, action):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "entity_id": f"{service}.{entity_id}"
    }
    service_url = f"{base_url}/api/services/{service.replace('.', '/')}/{action}"

    response = requests.post(service_url, json=payload, headers=headers)

    if response.status_code == 200:
        print(f"Le service {service} a été appelé avec succès pour l'entité {entity_id}.")
    else:
        print(f"Erreur lors de l'appel du service {service} pour l'entité {entity_id}. HTTP: {response.status_code}")


parser = argparse.ArgumentParser(description="Script pour déclencher des appels API Home Assistant")
parser.add_argument("--action", help="Action a mener sur le bouton salat", type=str)
args = parser.parse_args()

init_db()

service = get_value('homeassistant', 'SERVICE', 'input_boolean')
token = get_value('homeassistant', 'TOKEN')
base_url = get_value('homeassistant', 'URL')
entity_id = get_value('homeassistant', 'ENTITY_ID')

if not all([token, base_url, entity_id]):
    print("Erreur : configuration Home Assistant incomplète dans la base de données.")
    exit(1)

call_home_assistant(service, token, base_url, entity_id, args.action)
