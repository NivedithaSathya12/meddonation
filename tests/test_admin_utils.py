"""
Pytest tests for admin_utils functions.
Tests are safe to skip if database is missing.
"""

import pytest
import os
import sys
import time

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import admin_utils
from db_init import ensure_db


def setup_module():
    """Setup test database before running tests."""
    # Ensure database exists
    try:
        ensure_db()
    except Exception as e:
        pytest.skip(f"Database setup failed: {e}")


def test_insert_and_get_ngo():
    """
    Test inserting an NGO and then retrieving it.
    Uses unique name with timestamp to avoid conflicts.
    """
    # Check if database exists
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "meddonation.db")
    if not os.path.exists(db_path):
        pytest.skip("Database not found")
    
    # Insert a test NGO with unique name
    timestamp = int(time.time())
    test_name = f"Test NGO {timestamp}"
    test_city = "Test City"
    test_contact = "+91-12345-67890"
    test_accepts = "tablets"
    
    ngo_id = admin_utils.insert_ngo(test_name, test_city, test_contact, test_accepts)
    
    # Verify insertion was successful
    assert ngo_id is not None, "NGO insertion should return an ID"
    assert isinstance(ngo_id, int), "NGO ID should be an integer"
    assert ngo_id > 0, "NGO ID should be positive"
    
    # Retrieve all NGOs
    ngos_df = admin_utils.get_all_ngos()
    
    # Verify the NGO is in the dataframe
    assert not ngos_df.empty, "NGOs dataframe should not be empty"
    assert test_name in ngos_df['name'].values, f"Test NGO '{test_name}' should be in the dataframe"
    
    # Verify the data matches
    test_ngo = ngos_df[ngos_df['name'] == test_name].iloc[0]
    assert test_ngo['city'] == test_city, "City should match"
    assert test_ngo['contact'] == test_contact, "Contact should match"
    assert test_ngo['accepts'] == test_accepts, "Accepts should match"
    
    # Cleanup: try to delete (if delete function exists, otherwise just verify)
    # Note: We don't have a delete_ngo function, so we'll leave the test data
    # In production, you might want to add cleanup


def test_insert_and_get_shelf_life():
    """
    Test inserting a shelf life entry and then retrieving it.
    Uses unique medicine name with timestamp to avoid conflicts.
    """
    # Check if database exists
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "meddonation.db")
    if not os.path.exists(db_path):
        pytest.skip("Database not found")
    
    # Insert a test shelf life entry with unique name
    timestamp = int(time.time())
    test_medicine = f"Test Medicine {timestamp}"
    test_months = 24
    test_notes = "Test notes"
    
    success = admin_utils.insert_shelf(test_medicine, test_months, test_notes)
    
    # Verify insertion was successful
    assert success is True, "Shelf life insertion should return True"
    
    # Retrieve all shelf life entries
    shelf_df = admin_utils.get_all_shelf_life()
    
    # Verify the entry is in the dataframe
    assert not shelf_df.empty, "Shelf life dataframe should not be empty"
    assert test_medicine in shelf_df['medicine_name'].values, \
        f"Test medicine '{test_medicine}' should be in the dataframe"
    
    # Verify the data matches
    test_entry = shelf_df[shelf_df['medicine_name'] == test_medicine].iloc[0]
    assert test_entry['shelf_months'] == test_months, "Shelf months should match"
    assert test_entry['notes'] == test_notes, "Notes should match"
