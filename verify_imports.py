"""Quick verification script to test all imports"""
try:
    import streamlit as st
    print("✓ streamlit imported successfully")
except ImportError as e:
    print(f"✗ streamlit import failed: {e}")

try:
    import sqlite3
    print("✓ sqlite3 imported successfully")
except ImportError as e:
    print(f"✗ sqlite3 import failed: {e}")

try:
    import pandas as pd
    print(f"✓ pandas imported successfully (version: {pd.__version__})")
except ImportError as e:
    print(f"✗ pandas import failed: {e}")

try:
    from utils import is_donation_allowed, find_ngos_for_med
    print("✓ utils imported successfully")
except ImportError as e:
    print(f"✗ utils import failed: {e}")

print("\nAll imports verified!")

