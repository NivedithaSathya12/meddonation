# check_db.py
import sqlite3
from pathlib import Path

db_path = Path("meddonation.db")
print("Looking for:", db_path.resolve())
if not db_path.exists():
    print("meddonation.db NOT found in the current folder.")
    print("Make sure you've copied meddonation_full_with_users.db -> meddonation.db")
    raise SystemExit(1)

con = sqlite3.connect(str(db_path))
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

print("Users sample:")
for r in cur.execute("SELECT id, username, role, ngo_id FROM users LIMIT 12"):
    print(r)

print("NGOs count:", cur.execute("SELECT COUNT(*) FROM ngos").fetchone()[0])
print("Donations count:", cur.execute("SELECT COUNT(*) FROM donations").fetchone()[0])

con.close()
