# db_init.py
"""
Use: python db_init.py [--reset]
Creates meddonationn.db in the same folder (seeded).
--reset will remove existing DB first.
"""
import argparse
from pathlib import Path
from app import DB_PATH, seed_database

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete existing DB before creating")
    args = parser.parse_args()
    p = Path(DB_PATH)
    if args.reset and p.exists():
        confirm = input(f"Delete existing DB at {DB_PATH}? Type YES to confirm: ")
        if confirm == "YES":
            p.unlink()
            print("Deleted", DB_PATH)
        else:
            print("Aborted.")
            return
    seed_database(DB_PATH)
    print("DB initialized at", DB_PATH)

if __name__ == "__main__":
    main()
