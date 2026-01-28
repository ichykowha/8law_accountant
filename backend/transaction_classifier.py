# backend/transaction_classifier.py
from backend.database.connection import get_db
from backend.database.models import Transaction
from sqlalchemy.orm import Session
from typing import List

# Simple rule-based classifier (placeholder for AI/ML)
def classify_transaction(txn: Transaction) -> str:
    desc = (txn.description or "").lower()
    if "grocery" in desc:
        return "Groceries"
    if "uber" in desc or "lyft" in desc:
        return "Transport"
    if "rent" in desc:
        return "Rent"
    if "salary" in desc or "payroll" in desc:
        return "Income"
    return "Uncategorized"

# Batch classify all unclassified transactions
def batch_classify(user_id: int):
    db: Session = next(get_db())
    txns: List[Transaction] = db.query(Transaction).filter(Transaction.user_id == user_id, (Transaction.category == None) | (Transaction.category == "")).all()
    for txn in txns:
        txn.category = classify_transaction(txn)
    db.commit()
    return len(txns)

# Placeholder for AI/ML model integration
def ai_classify_transaction(txn: Transaction):
    pass
