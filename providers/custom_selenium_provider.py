"""
[CONCEPT] custom_selenium_provider.py

Provider pour scraper le site web DIRECT d'une mosquée, sans passer par mawaqit.net.
Destiné aux développeurs qui veulent pointer vers un site de mosquée spécifique.

Pour l'utiliser :
  1. Activer dans get_time_salat.py (voir commentaire dans ce fichier)
  2. Adapter les constantes WAIT_SELECTOR et PRAYER_SELECTORS ci-dessous
     à la structure HTML du site cible
  3. Passer n'importe quelle URL dans MOSQUE_URL

État : CONCEPT — non connecté au reste du projet.
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC


# ---------------------------------------------------------------------------
# ZONE DE CUSTOMISATION
# Adapter ces sélecteurs à la structure HTML du site cible.
# ---------------------------------------------------------------------------

# Sélecteur CSS ou XPath à attendre avant de commencer le scraping
# (preuve que la page est chargée)
WAIT_SELECTOR = (By.XPATH, "//div[@class='prayers']")
WAIT_TIMEOUT  = 10  # secondes

# Sélecteur pour chaque prière.
# Chaque entrée : (nom_priere, By.XXX, "expression")
# L'élément trouvé doit contenir l'heure au format "HH:MM"
PRAYER_SELECTORS = [
    ("Fajr",    By.XPATH, "//div[@class='name' and contains(text(), 'Fajr')]/following-sibling::div[@class='time']/div"),
    ("Dhuhr",   By.XPATH, "//div[@class='name' and contains(text(), 'Dhuhr')]/following-sibling::div[@class='time']/div"),
    ("Asr",     By.XPATH, "//div[@class='name' and contains(text(), 'Asr')]/following-sibling::div[@class='time']/div"),
    ("Maghrib", By.XPATH, "//div[@class='name' and contains(text(), 'Maghrib')]/following-sibling::div[@class='time']/div"),
    ("Isha",    By.XPATH, "//div[@class='name' and contains(text(), 'Isha')]/following-sibling::div[@class='time']/div"),
]

# Délai supplémentaire après chargement de la page (en secondes)
# Utile si le site injecte les horaires via JavaScript après le chargement initial
EXTRA_WAIT = 2

# ---------------------------------------------------------------------------
# FIN DE LA ZONE DE CUSTOMISATION
# ---------------------------------------------------------------------------


def get_prayer_times(url):
    """
    Scrape les horaires de prière depuis n'importe quel site de mosquée.
    Retourne une liste de tuples (nom, heure, minute).

    Adapte PRAYER_SELECTORS à la structure HTML du site cible.
    """
    options = Options()
    options.add_argument("-headless")

    service = Service('/usr/local/bin/geckodriver', log_output=os.devnull)
    browser = webdriver.Firefox(service=service, options=options)
    browser.get(url)

    results = []
    try:
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            EC.presence_of_element_located(WAIT_SELECTOR)
        )
        if EXTRA_WAIT > 0:
            time.sleep(EXTRA_WAIT)

        for prayer_name, by, selector in PRAYER_SELECTORS:
            try:
                element = browser.find_element(by, selector)
                hour, minute = element.text.strip().split(':')
                results.append((prayer_name, hour, minute))
            except NoSuchElementException as e:
                print(f"[custom_selenium] Prière {prayer_name} introuvable. Erreur : {e}")
            except Exception as e:
                print(f"[custom_selenium] Erreur inattendue pour {prayer_name} : {e}")

    except Exception as e:
        print(f"[custom_selenium] Erreur lors du chargement de la page : {e}")
    finally:
        browser.quit()

    return results
