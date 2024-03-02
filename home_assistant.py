import requests

url = "http://homeassistant:8123/api/services/media_player/play_media"

headers = {
    "Authorization": "Bearer VOTRE_TOKEN_LONGUE_DURÉE",
    "content-type": "application/json",
}

data = {
    "entity_id": "media_player.votre_home_pod",
    "media_content_id": "http://adresse_de_votre_serveur/adhan.mp3",
    "media_content_type": "music"
}

response = requests.post(url, headers=headers, json=data)

print(response.text)
