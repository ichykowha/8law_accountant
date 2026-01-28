# backend/reconciliation.py
from backend.database.connection import get_db
from backend.database.models import Transaction
from sqlalchemy.orm import Session
from typing import List, Dict

def find_potential_matches(user_id, amount, date, vendor=None, days_window=3) -> List[Dict]:
    db: Session = next(get_db())
    # Find transactions within a date window and similar amount
    query = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.amount == amount,
        Transaction.date.between(date - pd.Timedelta(days=days_window), date + pd.Timedelta(days=days_window))
    )
    if vendor:
        query = query.filter(Transaction.vendor == vendor)
    return [t for t in query.all()]

def reconcile_transaction(txn_id, match_id):
    db: Session = next(get_db())
    txn = db.query(Transaction).get(txn_id)
    match = db.query(Transaction).get(match_id)
    if txn and match:
        txn.status = "reconciled"
        match.status = "reconciled"
        db.commit()
        return True
    return False

# Placeholder for AI/ML reconciliation
# def ai_reconcile(transactions: List[Transaction]) -> ...
