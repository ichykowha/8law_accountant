# backend/month_end_close.py
from datetime import datetime, timezone
from typing import List, Dict, Optional
from backend.logic.ledger import JournalEntry
from backend.logic.doc_classifier import detect_doc_type
from backend.logic.ledger import default_coa
from backend.audit_logger import log_action
import random


# Dynamic checklist generator (AI/ML placeholder)
def generate_checklist(user_id: int, company_type: Optional[str] = None, anomalies: Optional[List[str]] = None) -> List[Dict]:
    # Example: add tasks based on company type or anomalies
    checklist = [
        {"task": "Reconcile all bank accounts", "auto": True},
        {"task": "Review all transactions", "auto": False},
        {"task": "Generate financial statements", "auto": True},
        {"task": "Review flagged transactions", "auto": False},
        {"task": "Export audit log", "auto": True},
    ]
    if company_type == "nonprofit":
        checklist.append({"task": "Review grant allocations", "auto": False})
    if anomalies:
        for a in anomalies:
            checklist.append({"task": f"Review anomaly: {a}", "auto": False})
    # Add AI-powered suggestions (placeholder)
    checklist.append({"task": "Review AI suggestions for next steps", "auto": False, "help": "AI will suggest actions based on your data."})
    return checklist
    return checklist

import time
# In-memory store for demo
CLOSE_STATUS = {}
CLOSE_META = {}
TASK_TIMELINE = {}

# In-memory store for demo
CLOSE_STATUS = {}

def get_checklist(user_id) -> List[Dict]:
    meta = CLOSE_META.get(user_id, {})
    checklist = CLOSE_STATUS.get(user_id)
    if checklist is None:
        # Generate dynamic checklist
        checklist = []
        for t in generate_checklist(user_id, meta.get("company_type"), meta.get("anomalies")):
            checklist.append({
                "task": t["task"],
                "completed": False,
                "auto": t.get("auto", False),
                "help": t.get("help", "")
            })
        CLOSE_STATUS[user_id] = checklist
    return checklist

def complete_task(user_id, task):
    checklist = get_checklist(user_id)
    now = time.time()
    for t in checklist:
        if t["task"] == task:
            t["completed"] = True
            log_action(user_id, "month_end_task_completed", {"task": task})
            # Timeline: record completion timestamp
            if user_id not in TASK_TIMELINE:
                TASK_TIMELINE[user_id] = {}
            TASK_TIMELINE[user_id][task] = now
    CLOSE_STATUS[user_id] = checklist
    # If all tasks complete, trigger auto-close
    if all(t["completed"] for t in checklist):
        log_action(user_id, "month_end_auto_close", {"status": "success"})

# AI/ML automation: auto-complete tasks based on data (placeholder logic)
def auto_complete_tasks(user_id):
    checklist = get_checklist(user_id)
    # Example: if all journal entries are balanced, mark reconciliation as done
    # (Replace with real logic)
    for t in checklist:
        if t["auto"]:
            t["completed"] = True
            log_action(user_id, "month_end_task_autocompleted", {"task": t["task"]})
    CLOSE_STATUS[user_id] = checklist
    # If all tasks complete, trigger auto-close
    if all(t["completed"] for t in checklist):
        log_action(user_id, "month_end_auto_close", {"status": "success"})

# Smart reminders/notifications (placeholder)
def get_outstanding_tasks(user_id):
    return [t["task"] for t in get_checklist(user_id) if not t["completed"]]

def send_reminder(user_id, email: str):
    outstanding = get_outstanding_tasks(user_id)
    if outstanding:
        # Integrate with notification system here
        log_action(user_id, "reminder_sent", {"tasks": outstanding, "email": email})
        return True
    return False

# AI-generated summary report (placeholder)
# AI-generated summary report (placeholder)
# AI-generated summary report (enhanced)
def generate_summary_report(user_id) -> str:
    checklist = get_checklist(user_id)
    completed = [t["task"] for t in checklist if t["completed"]]
    outstanding = [t["task"] for t in checklist if not t["completed"]]
    report = f"Month-End Close Summary for User {user_id}\n"
    report += f"Completed Tasks: {completed}\n"
    report += f"Outstanding Tasks: {outstanding}\n"
    # AI/ML: Add risk highlights, suggestions, etc.
    if outstanding:
        report += "\nRisks: Outstanding tasks may delay close.\n"
        report += "AI Suggestions: " + get_ai_suggestions(user_id) + "\n"
    else:
        report += "\nAll tasks complete. No risks detected.\n"
    # Add anomaly detection summary
    anomalies = detect_anomalies(user_id)
    if anomalies:
        report += f"\nAnomalies detected: {anomalies}\n"
    return report

# AI-powered suggestions for next steps (real data hook)
def get_ai_suggestions(user_id) -> str:
    # Example: check for missing bank statements or unreconciled accounts
    # In real implementation, pull from DB or API
    missing_docs = get_missing_documents(user_id)
    unreconciled = get_unreconciled_accounts(user_id)
    if missing_docs:
        return f"Missing documents: {', '.join(missing_docs)}. Please upload."
    if unreconciled:
        return f"Unreconciled accounts: {', '.join(unreconciled)}. Please review."
    return "All key documents and accounts appear complete."

# Example: scan for missing documents (stub)
def get_missing_documents(user_id) -> list:
    # Replace with real document check
    # For demo, randomly return a missing doc
    docs = ["bank_statement_jan.pdf", "invoice_123.pdf"]
    if random.random() < 0.5:
        return [random.choice(docs)]
    return []

# Example: scan for unreconciled accounts (stub)
def get_unreconciled_accounts(user_id) -> list:
    # Replace with real reconciliation check
    accounts = ["Chequing", "Savings", "Credit Card"]
    if random.random() < 0.5:
        return [random.choice(accounts)]
    return []

# Anomaly detection (real data hook)
def detect_anomalies(user_id) -> list:
    # Example: flag if more than N transactions in a day (stub)
    # Replace with real transaction analysis
    if random.random() < 0.3:
        return ["Unusual transaction volume detected."]
    return []

# Contextual help for checklist items
# Contextual help for checklist items
def get_task_help(user_id, task_name) -> str:
    checklist = get_checklist(user_id)
    for t in checklist:
        if t["task"] == task_name:
            return t.get("help", "No additional info.")
    return "No additional info."

# 'What's missing?' feature
def whats_missing(user_id) -> str:
    missing_docs = get_missing_documents(user_id)
    unreconciled = get_unreconciled_accounts(user_id)
    if not missing_docs and not unreconciled:
        return "Nothing appears to be missing."
    msg = ""
    if missing_docs:
        msg += f"Missing documents: {', '.join(missing_docs)}. "
    if unreconciled:
        msg += f"Unreconciled accounts: {', '.join(unreconciled)}. "
    return msg.strip()

# User feedback on AI suggestions
import json
AI_FEEDBACK = {}
FEEDBACK_FILE = "data/ai_feedback.json"
def submit_feedback(user_id, feedback: str):
    if user_id not in AI_FEEDBACK:
        AI_FEEDBACK[user_id] = []
    entry = {"user_id": user_id, "feedback": feedback, "timestamp": datetime.now(timezone.utc).isoformat()}
    AI_FEEDBACK[user_id].append(entry)
    # Persist feedback to file for retraining
    try:
        all_feedback = []
        # Load existing feedback
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                all_feedback = json.load(f)
        except Exception:
            pass
        all_feedback.append(entry)
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(all_feedback, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not persist feedback: {e}")

# Export feedback for model retraining
def export_feedback() -> list:
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# Progress analytics
# Progress analytics
def get_progress(user_id) -> float:
    checklist = get_checklist(user_id)
    if not checklist:
        return 0.0
    completed = sum(1 for t in checklist if t["completed"])
    return completed / len(checklist)

# Timeline analytics
def get_timeline(user_id):
    """Returns a list of (task, completed, timestamp) for the user's close process."""
    checklist = get_checklist(user_id)
    timeline = []
    user_timeline = TASK_TIMELINE.get(user_id, {})
    for t in checklist:
        ts = user_timeline.get(t["task"])
        timeline.append({
            "task": t["task"],
            "completed": t["completed"],
            "timestamp": ts
        })
    return timeline

def predict_completion_date(user_id):
    """Predicts completion date based on current pace (simple linear extrapolation)."""
    timeline = get_timeline(user_id)
    completed = [t for t in timeline if t["completed"] and t["timestamp"]]
    if not completed:
        return None
    start = min(t["timestamp"] for t in completed)
    now = time.time()
    rate = len(completed) / (now - start) if (now - start) > 0 else 0
    remaining = len([t for t in timeline if not t["completed"]])
    if rate == 0:
        return None
    seconds_left = remaining / rate
    return now + seconds_left

def get_bottlenecks(user_id):
    """Returns tasks that are taking the longest to complete."""
    timeline = get_timeline(user_id)
    incomplete = [t for t in timeline if not t["completed"]]
    if not incomplete:
        return []
    # For demo, just return the first outstanding task
    return [incomplete[0]["task"]]

# Natural language Q&A (Google Gemini LLM integration)
import os
import requests
import json
def answer_question(user_id, question: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "LLM API key not set. Please set GEMINI_API_KEY in your environment."
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    prompt = f"You are 6law, an expert AI accounting assistant. User context: user_id={user_id}. Question: {question}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256}
    }
    try:
        resp = requests.post(f"{endpoint}?key={api_key}", headers=headers, data=json.dumps(data), timeout=10)
        resp.raise_for_status()
        out = resp.json()
        return out["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"LLM error: {e}"
