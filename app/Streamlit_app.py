import os
import sys

# Ensure repo root is on sys.path so we can import app.frontend and backend.*
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.frontend import main

main()
