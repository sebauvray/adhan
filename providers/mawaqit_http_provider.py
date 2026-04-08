import re
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse

PRAYERS = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
# calendar entries: [Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha]
# We skip index 1 (Sunrise) → indices [0, 2, 3, 4, 5]
CALENDAR_INDICES = [0, 2, 3, 4, 5]


def _extract_slug(url):
    """
    Extract slug from a mawaqit.net URL.
    Ex: https://mawaqit.net/fr/m/grande-mosquee-paris → grande-mosquee-paris
    """
    host = urlparse(url).netloc
    if 'mawaqit.net' not in host:
        raise ValueError(f"URL invalide : ce provider n'accepte que les URLs mawaqit.net (reçu : {url})")
    path = urlparse(url).path.rstrip('/')
    return path.split('/')[-1]


def _fetch_conf_data(url):
    """Fetch and parse confData from a mawaqit.net page."""
    slug = _extract_slug(url)

    response = requests.get(
        f"https://mawaqit.net/fr/m/{slug}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; AdhanHome/1.0)"},
        timeout=10,
    )
    response.raise_for_status()

    match = re.search(r'confData\s*=\s*(\{.+\});', response.text)
    if not match:
        raise ValueError("confData introuvable dans la page mawaqit")

    conf = json.loads(match.group(1))
    return conf, slug


def _get_day_from_calendar(conf, target_date):
    """
    Extract prayer times for a specific date from conf.calendar.

    conf.calendar[month_index][day] contains the actual prayer times
    set by the mosque (adjusted by the imam), as 6 values:
    [Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha]

    Returns list of 5 time strings [Fajr, Dhuhr, Asr, Maghrib, Isha] or None.
    """
    month_index = target_date.month - 1
    day_key = str(target_date.day)

    calendar = conf.get('calendar', [])
    if not calendar or len(calendar) <= month_index:
        return None

    month_data = calendar[month_index]
    if isinstance(month_data, dict):
        day_times = month_data.get(day_key)
    elif isinstance(month_data, list) and len(month_data) > target_date.day:
        day_times = month_data[target_date.day]
    else:
        return None

    if not day_times or len(day_times) < 6:
        return None

    return [day_times[i] for i in CALENDAR_INDICES], day_times[1]


def _get_adhan_times_from_calendar(conf, use_next_day=False):
    """
    Extract adhan times from conf.calendar.
    If use_next_day is True and all prayers are past, return tomorrow's times.
    Returns (prayer_times, sunrise) or (None, None).
    """
    now = datetime.now()
    result = _get_day_from_calendar(conf, now)
    if result is None:
        return None, None
    today_times, sunrise = result

    if use_next_day and today_times:
        last_prayer = today_times[-1]
        h, m = map(int, last_prayer.split(':'))
        if now.time() > now.replace(hour=h, minute=m, second=0).time():
            tomorrow = now + timedelta(days=1)
            result_tomorrow = _get_day_from_calendar(conf, tomorrow)
            if result_tomorrow:
                return result_tomorrow

    return today_times, sunrise


def _compute_iqama_times(adhan_times, conf, target_date=None):
    """
    Compute iqama times by adding iqamaCalendar delays to adhan times.

    iqamaCalendar structure: list of 12 months, each month is a dict of days,
    each day is a list of 5 delay strings: ["+15", "+10", "+10", "+5", "+10"]

    Falls back to adhan times if iqamaCalendar is missing.
    """
    iqama_calendar = conf.get('iqamaCalendar')
    if not iqama_calendar:
        return adhan_times

    ref = target_date or datetime.now()
    month_index = ref.month - 1
    day_key = str(ref.day)

    # iqamaCalendar[month_index][day_key] = ["+15", "+10", ...]
    if len(iqama_calendar) <= month_index:
        return adhan_times

    month_data = iqama_calendar[month_index]
    if not isinstance(month_data, dict) or day_key not in month_data:
        return adhan_times

    delays = month_data[day_key]
    if not delays or len(delays) < 5:
        return adhan_times

    iqama_times = []
    for adhan_str, delay_str in zip(adhan_times, delays):
        try:
            delay_min = int(str(delay_str).strip().lstrip('+'))
            h, m = map(int, adhan_str.split(':'))
            iqama_dt = datetime(2000, 1, 1, h, m) + timedelta(minutes=delay_min)
            iqama_times.append(iqama_dt.strftime('%H:%M'))
        except (ValueError, TypeError):
            iqama_times.append(adhan_str)

    return iqama_times


def get_prayer_times(url):
    """
    Fetch today's adhan times from mawaqit.net.
    Returns a list of tuples (name, hour, minute) for the crontab.

    Uses conf.calendar (mosque-adjusted times), falls back to conf.times (astronomical).
    """
    conf, slug = _fetch_conf_data(url)

    adhan_times, _ = _get_adhan_times_from_calendar(conf, use_next_day=False)
    if not adhan_times:
        adhan_times = conf.get('times', [])[:5]
        print(f"[mawaqit] Calendar unavailable, using conf.times as fallback")

    if not adhan_times or len(adhan_times) < 5:
        raise ValueError(f"Horaires introuvables dans confData")

    results = []
    for name, time_str in zip(PRAYERS, adhan_times):
        hour, minute = time_str.split(':')
        results.append((name, hour, minute))

    print(f"Horaires récupérés depuis mawaqit.net ({slug}) : {adhan_times}")
    return results


def get_full_data(url):
    """
    Fetch all mawaqit data: adhan times, iqama times, city, coordinates.

    Data sources in confData:
    - calendar[month][day]  : actual prayer times displayed by the mosque (6 values)
    - iqamaCalendar         : delay offsets to add for iqama ["+15","+10","+10","+5","+10"]
    - times                 : raw astronomical times (fallback only)
    - name / city           : mosque or city name
    - latitude / longitude  : GPS coordinates
    """
    conf, slug = _fetch_conf_data(url)

    adhan_times, sunrise = _get_adhan_times_from_calendar(conf, use_next_day=True)
    if not adhan_times:
        adhan_times = conf.get('times', [])[:5]
        sunrise = None

    if not adhan_times or len(adhan_times) < 5:
        raise ValueError("Horaires introuvables dans confData")

    iqama_times = _compute_iqama_times(adhan_times, conf)

    prayers = []
    for name, adhan_time, iqama_time in zip(PRAYERS, adhan_times, iqama_times):
        prayers.append({
            'name': name,
            'adhan': adhan_time,
            'iqama': iqama_time,
        })

    # Extract city from "Mosquée X - CityName" format
    raw_name = conf.get('name', '')
    if ' - ' in raw_name:
        city = raw_name.split(' - ')[-1].strip()
    else:
        city = raw_name

    return {
        'prayers': prayers,
        'city': city,
        'mosque_name': raw_name,
        'lat': conf.get('latitude', conf.get('lat')),
        'lng': conf.get('longitude', conf.get('lng')),
        'slug': slug,
        'sunrise': sunrise,
    }


def get_full_data_for_date(url, target_date):
    """
    Fetch mawaqit data for a specific date.
    Used by get_time_salat.py to fetch today or tomorrow's data.
    """
    conf, slug = _fetch_conf_data(url)

    result = _get_day_from_calendar(conf, target_date)
    if result:
        adhan_times, sunrise = result
    else:
        adhan_times = conf.get('times', [])[:5]
        sunrise = None

    if not adhan_times or len(adhan_times) < 5:
        raise ValueError("Horaires introuvables dans confData")

    iqama_times = _compute_iqama_times(adhan_times, conf, target_date=target_date)

    prayers = []
    for name, adhan_time, iqama_time in zip(PRAYERS, adhan_times, iqama_times):
        prayers.append({'name': name, 'adhan': adhan_time, 'iqama': iqama_time})

    raw_name = conf.get('name', '')
    city = raw_name.split(' - ')[-1].strip() if ' - ' in raw_name else raw_name

    jumua = [j for j in [conf.get('jumua'), conf.get('jumua2'), conf.get('jumua3')] if j]

    return {
        'prayers': prayers,
        'city': city,
        'mosque_name': raw_name,
        'lat': conf.get('latitude', conf.get('lat')),
        'lng': conf.get('longitude', conf.get('lng')),
        'slug': slug,
        'jumua': jumua,
        'sunrise': sunrise,
    }
