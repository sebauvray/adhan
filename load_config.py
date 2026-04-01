#!/usr/bin/env python3
"""
Charge la configuration depuis SQLite et l'exporte comme variables shell.
Usage dans adhan.sh : eval "$(python3 /app/load_config.py)"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import get_value

init_db()


def export(name, table, key, default=''):
    value = get_value(table, key, default)
    value = str(value).replace("'", "'\\''")
    print(f"export {name}='{value}'")


export('OWNTONE_HOST',   'owntone', 'HOST')
export('OWNTONE_PORT',   'owntone', 'PORT', '3689')
export('ADHAN_FILE',     'owntone', 'ADHAN_FILE', '/srv/media/adhan.mp3')
export('ADHAN_VOLUME',   'owntone', 'ADHAN_VOLUME', '40')
export('LOG_LEVEL',      'config',  'LOG_LEVEL', 'INFO')
export('MORNING_TIME',   'config',  'MORNING_TIME', '07:00-11:00')
export('AFTERNOON_TIME', 'config',  'AFTERNOON_TIME', '11:00-20:00')
export('EVENING_TIME',   'config',  'EVENING_TIME', '20:00-06:00')
