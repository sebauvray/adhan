import os
import sys
from datetime import date, datetime, timedelta
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import (
    get_value, set_value, is_configured,
    save_prayer_times, has_prayer_times, cleanup_old_prayer_times
)
from providers.mawaqit_http_provider import get_full_data_for_date

BASH_SCRIPT_PATH = '/app/adhan.sh'

init_db()

cron_file_path = os.environ.get('PATH_CRON', '/etc/cron.d')
cron_file_name = 'salat'

print(f"Récupération des salats le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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


def fetch_and_store(target_date):
    """Fetch prayer times from mawaqit for a date and store in SQLite."""
    data = get_full_data_for_date(mosque_url, target_date)
    save_prayer_times(target_date.strftime('%Y-%m-%d'), data['prayers'])

    # Update city/coords/jumua if available
    if data.get('lat'):
        set_value('config', 'LAT', str(data['lat']))
    if data.get('lng'):
        set_value('config', 'LNG', str(data['lng']))
    if data.get('city'):
        set_value('config', 'CITY', data['city'])
    if data.get('jumua'):
        set_value('config', 'JUMUA', ','.join(data['jumua']))
    if data.get('sunrise'):
        set_value('config', 'SUNRISE', data['sunrise'])

    print(f"Horaires stockés pour le {target_date.strftime('%Y-%m-%d')} : "
          f"{[p['adhan'] for p in data['prayers']]}")
    return data['prayers']


def write_crontab(prayers):
    """Write crontab with prayer entries + self-refresh after Isha."""
    cron_lines = []

    # Self-refresh 5 min after Isha
    isha = next(p for p in prayers if p['name'] == 'Isha')
    ih, im = map(int, isha['adhan'].split(':'))
    refresh_dt = datetime(2000, 1, 1, ih, im) + timedelta(minutes=5)
    cron_lines.append(f"# Refresh après Isha\n")
    cron_lines.append(f"{refresh_dt.minute} {refresh_dt.hour} * * * root python3 /app/get_time_salat.py >> /var/log/cron.log 2>&1\n")

    # Prayer entries
    for p in prayers:
        h, m = map(int, p['adhan'].split(':'))
        cron_lines.append(f"# {p['name']}\n")
        cron_lines.append(f"{m} {h} * * * root bash {BASH_SCRIPT_PATH} {p['name']} >> /var/log/cron.log 2>&1\n")

    cron_lines.append("\n")

    os.makedirs(cron_file_path, exist_ok=True)
    cron_file_full_path = os.path.join(cron_file_path, cron_file_name)
    with open(cron_file_full_path, 'w') as f:
        f.writelines(cron_lines)
    os.chmod(cron_file_full_path, 0o644)

    print(f"Crontab mis à jour : {cron_file_full_path}")


check_url(mosque_url)

today = date.today()
tomorrow = today + timedelta(days=1)
now = datetime.now()

# Check if Isha is past (post-Isha refresh trigger)
from db.config import get_prayer_times_for_date
today_data = get_prayer_times_for_date(today.strftime('%Y-%m-%d'))
isha_today = next((p for p in today_data if p['name'] == 'Isha'), None) if today_data else None
isha_past = False
if isha_today:
    ih, im = map(int, isha_today['adhan'].split(':'))
    isha_past = now.hour > ih or (now.hour == ih and now.minute >= im)

if isha_past:
    # Post-Isha: fetch tomorrow, write crontab for tomorrow
    tomorrow_prayers = fetch_and_store(tomorrow)
    write_crontab(tomorrow_prayers)
    print("Crontab basculé sur les horaires de demain")
else:
    # Boot or during the day: fetch today, write crontab for today
    today_prayers = fetch_and_store(today)
    write_crontab(today_prayers)

cleanup_old_prayer_times()
