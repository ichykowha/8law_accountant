# tests/test_basic.py
import sys
import os
import pytest

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.admin import list_users

import sys
import os
import pytest

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.admin import list_users

def test_list_users():
    users = list_users()
    assert isinstance(users, list)
    assert len(users) > 0
