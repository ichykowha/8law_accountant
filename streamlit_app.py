# streamlit_app.py
import os
import sys

# Ensure repo root is on sys.path so we can import app.*
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Run preflight checks BEFORE importing the rest of the app
from app.preflight import run as preflight_run

preflight_run()

# Import after preflight so missing secrets fail fast with a clean message
import app.frontend as frontend


def main():
    frontend.main()


if __name__ == "__main__":
    main()
