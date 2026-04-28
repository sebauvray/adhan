import time
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC

PRAYERS = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']


def _normalize_url(url):
    """S'assure que l'URL pointe bien vers une page mawaqit.net."""
    host = urlparse(url).netloc
    if 'mawaqit.net' not in host:
        raise ValueError(f"URL invalide : ce provider n'accepte que les URLs mawaqit.net (reçu : {url})")
    return url


def get_prayer_times(url):
    """
    Récupère les horaires de prière depuis mawaqit.net via Selenium.
    Utile si la récupération HTTP échoue (JS requis, anti-bot, etc.).
    Retourne une liste de tuples (nom, heure, minute).
    """
    url = _normalize_url(url)

    options = Options()
    options.add_argument("-headless")

    service = Service('/usr/local/bin/geckodriver', log_output=os.devnull)
    browser = webdriver.Firefox(service=service, options=options)
    browser.get(url)

    results = []
    try:
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".salat-times"))
        )
        time.sleep(2)
        for prayer_name in PRAYERS:
            try:
                element = browser.find_element(
                    By.XPATH,
                    f"//div[@class='name' and contains(text(), '{prayer_name}')]"
                    f"/following-sibling::div[@class='time']/div"
                )
                hour, minute = element.text.strip().split(':')
                results.append((prayer_name, hour, minute))
            except NoSuchElementException as e:
                print(f"Prière {prayer_name} introuvable sur la page. Erreur : {str(e)}")
            except Exception as e:
                print(f"Erreur inattendue pour {prayer_name} : {str(e)}")
    except Exception as e:
        print(f"Erreur lors du chargement de la page mawaqit : {str(e)}")
    finally:
        browser.quit()

    return results
