import sqlite3, datetime, os
fn = "meddonationn.db"
# remove old bad file if present
if os.path.exists(fn):
    os.remove(fn)
conn = sqlite3.connect(fn)
cur = conn.cursor()
cur.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, ngo_id INTEGER);
CREATE TABLE ngos (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, city TEXT, contact TEXT, accepts TEXT);
CREATE TABLE shelf_life (id INTEGER PRIMARY KEY AUTOINCREMENT, medicine_name TEXT UNIQUE, shelf_months INTEGER, notes TEXT);
CREATE TABLE donations (id INTEGER PRIMARY KEY AUTOINCREMENT, donor_name TEXT, donor_city TEXT, medicine_name TEXT, batch_date TEXT, expiry_date TEXT, status TEXT, matched_ngo_id INTEGER, created_at TEXT);
CREATE TABLE audio_transcriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT, uploader TEXT, uploaded_at TEXT, transcription TEXT);
""")
# seed users (passwords hashed with sha256("medsalt"+password))
import hashlib
def h(p): return hashlib.sha256(("medsalt"+p).encode()).hexdigest()
users=[('admin',h('admin@123'),'admin',None),('ravi',h('ravi@123'),'donor',None),('sita',h('sita@123'),'donor',None),('helping_user',h('help@123'),'ngo',1)]
cur.executemany("INSERT INTO users (username,password_hash,role,ngo_id) VALUES (?,?,?,?)", users)
ngos=[("Helping Hands Trust","Bengaluru","+91 9000000001","paracetamol,ibuprofen"),
("Care for All","Mumbai","+91 9000000002","vitamins,antibiotics"),
("Asha Foundation","Hyderabad","+91 9000000003","antibiotics,paracetamol"),
("Sakhi NGO","Chennai","+91 9000000004","vitamins,antiacids"),
("Janseva","Delhi","+91 9000000005","paracetamol,antibiotics"),
("Grameen Care","Patna","+91 9000000006","vitamins,paracetamol"),
("Seva Samiti","Kolkata","+91 9000000007","cough syrups,antibiotics"),
("Rural Relief","Lucknow","+91 9000000008","paracetamol,vitamins"),
("Smile Foundation","Pune","+91 9000000009","general medicines"),
("Udaan Welfare","Jaipur","+91 9000000010","paracetamol,vitamins"),]
cur.executemany("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)", ngos)
shelf=[("Paracetamol",36,"Common painkiller"),("Ibuprofen",36,"NSAID"),("Amoxicillin",24,"Antibiotic"),("Azithromycin",24,"Antibiotic"),
("Cough Syrup",12,"Liquid formulation"),("Multivitamin",24,"Supplements"),("Antacid",36,"Stomach relief"),("Aspirin",36,"Painkiller"),
("Metformin",24,"Diabetes med"),("Vitamin C",36,"Supplement")]
cur.executemany("INSERT INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)", shelf)
donations=[("Ravi","Bengaluru","Paracetamol","2023-06-01","2026-06-01","pledged",1, datetime.datetime.now().isoformat()),
("Sita","Mumbai","Multivitamin","2024-01-01","","pledged",2, datetime.datetime.now().isoformat()),
("Ramesh","Delhi","Aspirin","2020-01-01","2021-01-01","rejected",5, datetime.datetime.now().isoformat())]
cur.executemany("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)", donations)
cur.execute("INSERT INTO audio_transcriptions (filename,filepath,uploader,uploaded_at,transcription) VALUES (?,?,?,?,?)", ("sample.wav","uploads/sample.wav","admin", datetime.datetime.now().isoformat(),"Sample text"))
conn.commit()
conn.close()
print("Created meddonationn.db successfully")
