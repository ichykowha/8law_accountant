# backend/ai_predictive.py
"""
Predictive analytics for tax/finance: anomaly detection, forecasting, and smarter classification.
"""
def detect_anomalies(transactions):
    # Placeholder: flag transactions over $10,000 as anomalies
    return [t for t in transactions if t.get('amount', 0) > 10000]

def predict_tax_liability(transactions):
    # Placeholder: sum all expenses as tax liability
    return sum(t.get('amount', 0) for t in transactions if t.get('type') == 'expense')

def classify_document(doc_text):
    # Placeholder: simple keyword-based classification
    if 'invoice' in doc_text.lower():
        return 'invoice'
    if 't4' in doc_text.lower():
        return 't4 slip'
    return 'unknown'
