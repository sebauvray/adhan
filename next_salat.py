from datetime import datetime, timedelta
import os

cron_file_path = service=os.environ.get('PATH_CRON')

def lire_crons(path):
    crons = []
    with open(path, 'r') as file:
        for line in file:
            if line.strip() and not line.startswith('#'):
                parts = line.split()
                hour = int(parts[1])
                minute = int(parts[0])
                name = line.split('#')[-1].strip()
                crons.append((name, hour, minute))
    return crons

def prochain_cron(crons):
    maintenant = datetime.now()
    prochains = []

    for cron in crons:
        name, hour, minute = cron
        cron_time = maintenant.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if cron_time < maintenant:
            cron_time += timedelta(days=1)
        prochains.append((name, cron_time))

    prochains.sort(key=lambda x: x[1])
    prochain = prochains[0]
    
    return [prochain[0], prochain[1].strftime("%H:%M")]


crons = lire_crons(cron_file_path)
prochain = prochain_cron(crons)
print(prochain)