import os
import sys
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import get_value, is_configured

BASH_SCRIPT_PATH = '/app/adhan.sh'

init_db()

cron_file_path = os.environ.get('PATH_CRON', '/etc/cron.d')
cron_file_name = 'salat.crontab'
autonomous = os.environ.get('AUTONOMOUS', 'false').lower() == 'true'

print(f"Récupération des salats le {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Mode : {'Mawaqit Selenium' if autonomous else 'Mawaqit HTTP'}")

if not is_configured():
    print("Projet non configuré. Accédez à l'interface web pour finaliser l'installation.")
    exit(0)

mosque_url = get_value('config', 'MOSQUE_URL')
if not mosque_url:
    print("Erreur : MOSQUE_URL non définie dans la configuration.")
    exit(1)


def check_url(url):
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; AdhanHome/1.0)"})
        if response.status_code == 404:
            print(f"Erreur : MOSQUE_URL introuvable (404). Vérifiez que l'URL de votre mosquée est correcte : {url}")
            exit(1)
        if response.status_code >= 400:
            print(f"Erreur : MOSQUE_URL a répondu {response.status_code}. URL : {url}")
            exit(1)
    except requests.exceptions.ConnectionError:
        print(f"Erreur : impossible de joindre {url}. Vérifiez votre connexion réseau et l'URL.")
        exit(1)
    except requests.exceptions.Timeout:
        print(f"Erreur : timeout en tentant de joindre {url} (délai > 10s).")
        exit(1)
    except requests.exceptions.InvalidURL:
        print(f"Erreur : MOSQUE_URL n'est pas une URL valide : {url}")
        exit(1)


check_url(mosque_url)

if autonomous:
    from providers.mawaqit_selenium_provider import get_prayer_times
    prayer_times = get_prayer_times(mosque_url)
else:
    from providers.mawaqit_http_provider import get_prayer_times
    prayer_times = get_prayer_times(mosque_url)

if not prayer_times:
    print("Aucun horaire récupéré. Le crontab ne sera pas modifié.")
    exit(1)

cron_lines = [f"0 4 * * * python3 /app/get_time_salat.py >> /var/log/cron.log \n"]
for name, hour, minute in prayer_times:
    cron_lines.append(f"# {name} \n")
    cron_lines.append(f"{minute} {hour} * * * bash {BASH_SCRIPT_PATH} {name} >> /var/log/cron.log \n")
cron_lines.append("\n")

os.makedirs(cron_file_path, exist_ok=True)
cron_file_full_path = os.path.join(cron_file_path, cron_file_name)
with open(cron_file_full_path, 'w') as f:
    f.writelines(cron_lines)

print(f"Crontab mis à jour : {cron_file_full_path}")
