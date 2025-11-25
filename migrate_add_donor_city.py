# migrate_add_donor_city.py
import sqlite3, shutil, sys, os

DB = "meddonationn.db"
BACKUP = DB + ".bak"

if not os.path.exists(DB):
    print("DB not found:", DB); sys.exit(1)

print("Backing up DB to", BACKUP)
shutil.copy2(DB, BACKUP)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# check existing columns
cur.execute("PRAGMA table_info('donations')")
cols = [row[1] for row in cur.fetchall()]
print("donations columns:", cols)

if "donor_city" in cols:
    print("Column donor_city already exists -> nothing to do")
else:
    print("Adding donor_city column...")
    cur.execute("ALTER TABLE donations ADD COLUMN donor_city TEXT;")
    conn.commit()
    print("Added donor_city")

# final check
cur.execute("PRAGMA table_info('donations')")
print("final columns:", [r[1] for r in cur.fetchall()])

conn.close()
print("DONE — your DB is now fixed. Restore from .bak if needed.")
