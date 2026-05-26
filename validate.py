import sqlite3
import sys

if len(sys.argv) < 4:
    print("Usage: python validate.py <user_id> <date YYYY-MM-DD> <prayer>")
    print("Example: python validate.py 1 2026-05-07 Isha")
    sys.exit(1)

user_id = int(sys.argv[1])
date = sys.argv[2]
prayer = sys.argv[3]

conn = sqlite3.connect('/app/data/adhan.db')

cols = [row[1] for row in conn.execute("PRAGMA table_info(prayer_logs)").fetchall()]
has_flags = 'on_time' in cols and 'in_group' in cols

if has_flags:
    cur = conn.execute(
        "INSERT OR IGNORE INTO prayer_logs (user_id, prayer, date, on_time, in_group) "
        "VALUES (?, ?, ?, 0, 0)",
        (user_id, prayer, date)
    )
else:
    cur = conn.execute(
        "INSERT OR IGNORE INTO prayer_logs (user_id, prayer, date) VALUES (?, ?, ?)",
        (user_id, prayer, date)
    )
conn.commit()

if cur.rowcount == 0:
    print(f"Already logged: {date} {prayer} (user {user_id})")
else:
    print(f"OK: {date} {prayer} validée pour user {user_id}")

conn.close()
