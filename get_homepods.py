#!/usr/bin/env python3
"""
Retourne les noms des HomePods actifs pour une période donnée.
Usage : python3 /app/get_homepods.py morning|afternoon|evening
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import get_homepods

if len(sys.argv) < 2:
    print("Usage: get_homepods.py <morning|afternoon|evening>", file=sys.stderr)
    sys.exit(1)

period = sys.argv[1]
init_db()

for pod in get_homepods():
    if pod.get(period):
        print(pod['name'])
