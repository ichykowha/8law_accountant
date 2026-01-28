# backend/review_assistant.py
from backend.database.connection import get_db
from backend.database.models import Transaction
from sqlalchemy.orm import Session
from typing import List, Dict

# Placeholder for AI/ML review logic
def summarize_books(user_id) -> Dict:
    db: Session = next(get_db())
    txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    total = sum(t.amount for t in txns)
    flagged = [t for t in txns if t.amount < 0 or t.status != "reconciled"]
    return {
        "total_transactions": len(txns),
        "total_amount": total,
        "flagged": flagged,
        "suggestions": ["Review negative or unreconciled transactions."]
    }

# def ai_review_books(...):
#     # Integrate with AI/ML model
#     pass
