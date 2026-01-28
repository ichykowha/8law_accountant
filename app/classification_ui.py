# app/classification_ui.py
import streamlit as st
from backend.transaction_classifier import batch_classify
from backend.database.connection import get_db
from backend.database.models import Transaction
from sqlalchemy.orm import Session

st.title("Transaction Classification")

user_id = 1  # Demo user
if st.button("Classify Unlabeled Transactions"):
    n = batch_classify(user_id)
    st.success(f"Classified {n} transactions.")

db: Session = next(get_db())
txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()

st.write("### Transactions")
for txn in txns:
    st.write(f"{txn.date.date()} | {txn.amount} | {txn.description} | Category: {txn.category}")
    new_cat = st.text_input(f"Edit category for {txn.id}", value=txn.category or "", key=f"cat_{txn.id}")
    if st.button(f"Update {txn.id}", key=f"update_{txn.id}"):
        txn.category = new_cat
        db.commit()
        st.success(f"Updated category for {txn.id}")
