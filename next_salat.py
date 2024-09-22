import re
import os
from datetime import datetime, timedelta

cron_file_path = os.environ.get('PATH_CRON')


def lire_salat_et_heures(path):
    resultats = []
    with open(path, 'r') as file:
        current_name = None
        for line in file:
            if line.strip().startswith('#'):
                current_name = line.strip().lstrip('#').strip()
            else:
                match = re.search(r'(\d{1,2}) (\d{1,2})', line)
                if match and current_name:
                    minute = match.group(1).zfill(2)
                    hour = match.group(2).zfill(2)
                    heure = f"{hour}:{minute}"
                    resultats.append([current_name, heure])
                    current_name = None

    return resultats


def prochaine_salat(salat_heures):
    maintenant = datetime.now()
    prochain_salat = None

    for salat in salat_heures:
        name, heure = salat
        salat_time = datetime.strptime(heure, "%H:%M").replace(year=maintenant.year, month=maintenant.month, day=maintenant.day)

        if salat_time > maintenant:
            prochain_salat = salat
            break

    if not prochain_salat:
        premier_salat = salat_heures[0]
        premier_time = datetime.strptime(premier_salat[1], "%H:%M").replace(year=maintenant.year, month=maintenant.month, day=maintenant.day) + timedelta(days=1)
        prochain_salat = [premier_salat[0], premier_time.strftime("%H:%M")]

    return prochain_salat

salat_heures = lire_salat_et_heures(cron_file_path)
prochain = prochaine_salat(salat_heures)

# Extraction du nom de la prière et de l'heure depuis la liste `prochain`
nom_salat = prochain[0]
heure_salat = prochain[1]

# Affichage du résultat dans un format lisible
print(f"La prochaine salat {nom_salat} sera à {heure_salat}")