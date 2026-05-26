import sqlite3
import sys

USER_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1

conn = sqlite3.connect('/app/data/adhan.db')
rows = conn.execute("""
WITH RECURSIVE
  prayers(name) AS (VALUES ('Fajr'),('Dhuhr'),('Asr'),('Maghrib'),('Isha')),
  dates(d) AS (
    SELECT MIN(date) FROM prayer_logs WHERE user_id = ?
    UNION ALL SELECT date(d,'+1 day') FROM dates WHERE d < date('now','localtime','-1 day')
  )
SELECT d.d, p.name FROM dates d CROSS JOIN prayers p
LEFT JOIN prayer_logs l ON l.date=d.d AND l.prayer=p.name AND l.user_id=?
WHERE l.id IS NULL
ORDER BY d.d, CASE p.name
  WHEN 'Fajr' THEN 1 WHEN 'Dhuhr' THEN 2 WHEN 'Asr' THEN 3
  WHEN 'Maghrib' THEN 4 ELSE 5 END;
""", (USER_ID, USER_ID)).fetchall()

from datetime import date as _date

JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

for d, prayer in rows:
    y, m, dd = map(int, d.split('-'))
    jour = JOURS[_date(y, m, dd).weekday()]
    print(f"{d}  {jour:<10}  {prayer}")

print(f"\nTotal: {len(rows)} prières manquantes")
