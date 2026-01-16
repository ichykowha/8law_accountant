import os
import sys
import json
import importlib

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def check_file(path, description):
    if os.path.exists(path):
        print(f"[{GREEN}FOUND{RESET}] {description}: {path}")
        return True
    else:
        print(f"[{RED}MISSING{RESET}] {description}: {path}")
        return False

def check_json(path):
    try:
        with open(path, 'r') as f:
            json.load(f)
        print(f"[{GREEN}VALID{RESET}] JSON Syntax: {path}")
        return True
    except json.JSONDecodeError as e:
        print(f"[{RED}INVALID{RESET}] JSON Syntax in {path}: {e}")
        return False
    except Exception as e:
        print(f"[{RED}ERROR{RESET}] Could not read {path}: {e}")
        return False

def check_import():
    print("-" * 30)
    print("Testing Logic Engine Import...")
    try:
        sys.path.append(os.getcwd())
        from backend.logic.t1_engine import T1DecisionEngine
        print(f"[{GREEN}SUCCESS{RESET}] T1DecisionEngine imported successfully.")
        
        # Try initializing to check if it finds the JSON
        try:
            engine = T1DecisionEngine(tax_year=2024)
            print(f"[{GREEN}SUCCESS{RESET}] Engine initialized (Rules loaded).")
        except Exception as e:
             print(f"[{RED}FAIL{RESET}] Engine crashed on startup: {e}")
             
    except ImportError as e:
        print(f"[{RED}FAIL{RESET}] Import Error: {e}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Unexpected Error: {e}")

if __name__ == "__main__":
    print("=== 8LAW DIAGNOSTIC TOOL ===\n")
    
    # 1. Check Directory Structure
    files_to_check = [
        ("app/main.py", "API Entry Point"),
        ("app/frontend.py", "Dashboard UI"),
        ("backend/logic/t1_engine.py", "Logic Engine"),
        ("backend/logic/rules_registry.py", "Rules Script"),
        ("backend/logic/rules_registry.json", "Tax Brackets Data"),
        ("backend/logic/__init__.py", "Logic Init File"),
        (".env", "Environment Variables")
    ]
    
    all_files_present = True
    for path, desc in files_to_check:
        if not check_file(path, desc):
            all_files_present = False

    # 2. Check JSON validity
    if os.path.exists("backend/logic/rules_registry.json"):
        check_json("backend/logic/rules_registry.json")

    # 3. Check Imports
    if all_files_present:
        check_import()
    else:
        print("\n[!] Fix missing files before testing logic.")

    print("\n============================")