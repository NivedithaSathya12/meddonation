# create_users.py
import sqlite3, hashlib, os
DB="meddonation.db"

def hash_password(password, salt="medsalt"):
    return hashlib.sha256((salt+password).encode('utf-8')).hexdigest()

conn = sqlite3.connect(DB)
c = conn.cursor()

# create users table
c.execute("""
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE,
  password_hash TEXT,
  role TEXT,     -- 'admin' / 'ngo' / 'donor'
  ngo_id INTEGER  -- nullable: links to ngos.id for NGO users
)
""")

# sample admin
admin_username = "admin"
admin_pw = "Admin@123"  # change this before production
c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
          (admin_username, hash_password(admin_pw), "admin", None))

# create NGO users for first 5 NGOs (example)
ngo_user_template = "ngo{}"
ngo_pw = "Ngo@1234"
c.execute("SELECT id FROM ngos LIMIT 5")
ngo_ids = [r[0] for r in c.fetchall()]
for i, nid in enumerate(ngo_ids, start=1):
    uname = f"ngo{i}"
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
              (uname, hash_password(ngo_pw), "ngo", nid))

conn.commit()
conn.close()
print("Users table created and sample users inserted.")
print("Admin user: username=admin password=Admin@123")
print("NGO users: ngo1..ngo5 password=Ngo@1234")
# create_users.py
import sqlite3, hashlib, os
DB="meddonation.db"

def hash_password(password, salt="medsalt"):
    return hashlib.sha256((salt+password).encode('utf-8')).hexdigest()

conn = sqlite3.connect(DB)
c = conn.cursor()

# create users table
c.execute("""
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE,
  password_hash TEXT,
  role TEXT,     -- 'admin' / 'ngo' / 'donor'
  ngo_id INTEGER  -- nullable: links to ngos.id for NGO users
)
""")

# sample admin
admin_username = "admin"
admin_pw = "Admin@123"  # change this before production
c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
          (admin_username, hash_password(admin_pw), "admin", None))

# create NGO users for first 5 NGOs (example)
ngo_user_template = "ngo{}"
ngo_pw = "Ngo@1234"
c.execute("SELECT id FROM ngos LIMIT 5")
ngo_ids = [r[0] for r in c.fetchall()]
for i, nid in enumerate(ngo_ids, start=1):
    uname = f"ngo{i}"
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
              (uname, hash_password(ngo_pw), "ngo", nid))

conn.commit()
conn.close()
print("Users table created and sample users inserted.")
print("Admin user: username=admin password=Admin@123")
print("NGO users: ngo1..ngo5 password=Ngo@1234")
