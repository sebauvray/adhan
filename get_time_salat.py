import sys
import time
import os
import requests
import datetime
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC



parser = argparse.ArgumentParser(description="Script pour récupérer les heures de prière.")
parser.add_argument("--url", help="URL de la mosquée pour récupérer les heures de prière", type=str)

args = parser.parse_args()

options = Options()
options.add_argument("-headless")
geckodriver_path = '/usr/local/bin/geckodriver'
timeWait = 5
cron_file_path = '/etc/cron.d'
cron_file_name = 'salat'
bash_script_path = '/app/adhan.sh'
cron_lines = []
url = args.url if args.url else os.environ.get('URL_MOSQUE')

if url is None:
    print("Aucune URL fournie. Veuillez passer une URL via --url ou définir la variable d'environnement URL_MOSQUE.")
    exit(1)

service = Service(geckodriver_path, log_output=os.devnull)
browser = webdriver.Firefox(service=service, options=options)
browser.get(url)

prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

print(f"Le script de récupération des salats s'est exécuté le {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


try:
    WebDriverWait(browser, timeWait).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[@class='prayers']"))
    )
    time.sleep(2) 
    for prayer_name in prayers:
        try:
            prayer_element = browser.find_element(By.XPATH, f"//div[@class='name' and contains(text(), '{prayer_name}')]/following-sibling::div[@class='time']/div")
            prayer_time = prayer_element.text
            hour, minute = prayer_time.split(':')
            cron_lines.append(f"{minute} {hour} * * * {bash_script_path} # {prayer_name}\n")
        except NoSuchElementException:
            print(f"Prayer {prayer_name} not found or an error occurred. Error: {str(e)}")
        except Exception as e:
            print(f"Erreur inattendue lors de la recherche de la prière {prayer_name}. Erreur: {str(e)}")
except Exception as e:
    print(f"An error occurred while loading the page: {str(e)}")
finally:
    browser.quit()

os.makedirs(cron_file_path, exist_ok=True)

cron_file_full_path = os.path.join(cron_file_path, cron_file_name)
with open(cron_file_full_path, 'w') as cron_file:
    cron_file.writelines(cron_lines)