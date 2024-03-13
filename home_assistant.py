import requests
import sys
import os
import argparse

def call_home_assistant(service, token, base_url, entity_id, action):
    """
    Fait un appel API à Home Assistant pour déclencher un service sur une entité spécifique.

    :param service: Le service à appeler, comme 'input_boolean.turn_on'.
    :param token: Le jeton d'accès longue durée pour l'API de Home Assistant.
    :param base_url: L'URL de base de l'instance Home Assistant, comme 'http://192.168.1.100:8123'.
    :param entity_id: L'ID de l'entité ciblée par l'appel du service.
    :param action: Action a mener sur l'entité.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "entity_id": f"{service}.{entity_id}"
    }

    # build url service
    service_url = f"{base_url}/api/services/{service.replace('.', '/')}/{action}"

    print(service_url)
    
    response = requests.post(service_url, json=payload, headers=headers)

    if response.status_code == 200:
        print(f"Le service {service} a été appelé avec succès pour l'entité {entity_id}.")
    else:
        print(f"Erreur lors de l'appel du service {service} pour l'entité {entity_id}. Réponse HTTP: {response.status_code}")



parser = argparse.ArgumentParser(description="Script pour déclencher des call api homeassitant.")
parser.add_argument("--action", help="Action a mener sur le bouton salat", type=str)

args = parser.parse_args()

service=os.environ.get('SERVICE')
token=os.environ.get('TOKEN')
base_url=os.environ.get('URL_HOMEASSISTANT')
entity_id=os.environ.get('ENTITY_ID')

print(entity_id)
call_home_assistant(service, token, base_url, entity_id, args.action)
