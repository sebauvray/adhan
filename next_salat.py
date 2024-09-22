import re
import os
from datetime import datetime, timedelta

# Path to the cron file (set this according to your environment)
cron_file_path = os.environ.get('PATH_CRON')

# Dictionary of prayer names with phonetic versions for Siri
phonetic_names = {
    "Fajr": "Fadjer",
    "Dhuhr": "Dour",
    "Asr": "Asser",
    "Maghrib": "Maghrib",
    "Isha": "Icha"
}

# Function to get the phonetic name for Siri
def get_phonetic_name(prayer_name):
    return phonetic_names.get(prayer_name, prayer_name)

# Function to read the lines and extract prayer names and associated times
def read_prayers_and_times(path):
    results = []
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
                    time = f"{hour}:{minute}"
                    results.append([current_name, time])
                    current_name = None

    return results

def next_prayer(prayer_times):
    now = datetime.now()
    next_prayer = None

    for prayer in prayer_times:
        name, time = prayer
        prayer_time = datetime.strptime(time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)

        if prayer_time > now:
            next_prayer = prayer
            break

    if not next_prayer:
        first_prayer = prayer_times[0]
        first_time = datetime.strptime(first_prayer[1], "%H:%M").replace(year=now.year, month=now.month, day=now.day) + timedelta(days=1)
        next_prayer = [first_prayer[0], first_time.strftime("%H:%M")]

    return next_prayer


prayer_times = read_prayers_and_times(cron_file_path)
next_prayer = next_prayer(prayer_times)

# Extract the prayer name and time from the `next_prayer` list
prayer_name = next_prayer[0]
prayer_time = next_prayer[1]
prayer_name_phonetic = get_phonetic_name(prayer_name)

# Display the result in a readable format
print(f"The next prayer {prayer_name_phonetic} will be at {prayer_time}")