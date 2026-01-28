# app/reconciliation_ui.py
import streamlit as st
from backend.database.connection import get_db
from backend.database.models import Transaction
from backend.reconciliation import find_potential_matches, reconcile_transaction
from sqlalchemy.orm import Session
import pandas as pd

st.title("Transaction Reconciliation")

user_id = 1  # Demo user

db: Session = next(get_db())
transactions = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.status == "pending").all()

if not transactions:
    st.info("No pending transactions to reconcile.")
else:
    for txn in transactions:
        st.write(f"**{txn.date.date()}** | {txn.amount} | {txn.description}")
        matches = find_potential_matches(user_id, txn.amount, txn.date, txn.vendor)
        if matches:
            st.write("Potential matches:")
            for match in matches:
                if st.button(f"Reconcile with {match.id}", key=f"rec_{txn.id}_{match.id}"):
                    if reconcile_transaction(txn.id, match.id):
                        st.success(f"Reconciled {txn.id} with {match.id}")
        else:
            st.warning("No matches found.")
