# app/transactions_ingest.py
import streamlit as st
import pandas as pd
from backend.database.connection import get_db
from backend.database.models import Transaction, User
from sqlalchemy.orm import Session
from datetime import datetime

st.title("Transaction Ingestion")

uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("Preview:", df.head())
    if st.button("Ingest Transactions"):
        db: Session = next(get_db())
        # For demo, assign all to user_id=1
        for _, row in df.iterrows():
            txn = Transaction(
                user_id=1,
                date=pd.to_datetime(row.get("date", datetime.now())),
                amount=row.get("amount", 0.0),
                description=row.get("description", ""),
                category=row.get("category", ""),
                vendor=row.get("vendor", ""),
                source="bank"
            )
            db.add(txn)
        db.commit()
        st.success(f"Ingested {len(df)} transactions.")
