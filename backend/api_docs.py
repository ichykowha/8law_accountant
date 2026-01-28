# backend/api_docs.py
"""
Auto-generate OpenAPI docs using FastAPI (scaffold).
"""
from fastapi import FastAPI
from backend.ai_predictive import detect_anomalies, predict_tax_liability

app = FastAPI(title="8law API")

@app.get("/anomalies")
def anomalies(transactions: list):
    return detect_anomalies(transactions)

@app.get("/predict_tax")
def predict_tax(transactions: list):
    return {"tax_liability": predict_tax_liability(transactions)}

# To run: uvicorn backend.api_docs:app --reload
