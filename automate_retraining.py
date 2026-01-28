# automate_retraining.py
"""
Automate retraining of AI/ML models using feedback data on a schedule or trigger.
This script can be run as a scheduled task (cron, Windows Task Scheduler) or called from your app.
"""
import subprocess
import sys
import time
import os

RETRAIN_SCRIPT = "retrain_model.py"
RETRAIN_INTERVAL_SECONDS = 24 * 60 * 60  # Once per day


def run_retraining():
    print("[Automate] Starting model retraining...")
    result = subprocess.run([sys.executable, RETRAIN_SCRIPT], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("[Automate] Retraining error:", result.stderr)
    print("[Automate] Retraining complete.")


def main():
    while True:
        run_retraining()
        print(f"[Automate] Sleeping for {RETRAIN_INTERVAL_SECONDS // 3600} hours...")
        time.sleep(RETRAIN_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
