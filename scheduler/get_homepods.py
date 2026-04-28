#!/usr/bin/env python3
"""
Returns the output names configured for a specific prayer.
Usage: python3 /app/get_homepods.py Fajr
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import get_outputs_for_prayer

if len(sys.argv) < 2:
    print("Usage: get_homepods.py <prayer_name>", file=sys.stderr)
    sys.exit(1)

prayer = sys.argv[1]
init_db()

for name in get_outputs_for_prayer(prayer):
    print(name)
