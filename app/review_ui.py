# app/review_ui.py
import streamlit as st
from backend.review_assistant import summarize_books

st.title("AI Review Assistant")

user_id = 1  # Demo user
summary = summarize_books(user_id)

st.write(f"Total transactions: {summary['total_transactions']}")
st.write(f"Total amount: {summary['total_amount']}")

if summary['flagged']:
    st.warning(f"Flagged transactions: {len(summary['flagged'])}")
    for t in summary['flagged']:
        st.write(f"{t.date.date()} | {t.amount} | {t.description} | Status: {t.status}")
else:
    st.success("No issues detected.")

st.markdown("**Suggestions:**")
for s in summary['suggestions']:
    st.info(s)
