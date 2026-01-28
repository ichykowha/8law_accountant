# backend/compliance.py
"""
Automated compliance checks and audit readiness scoring for 8law.
"""
def check_compliance(transactions, docs):
    # Placeholder: check if all required docs are present and no anomalies
    required_docs = {"t4", "invoice", "bank_statement"}
    doc_types = {d.get('type') for d in docs}
    missing = required_docs - doc_types
    score = 100 - (len(missing) * 20)
    return {
        "missing_docs": list(missing),
        "score": max(score, 0),
        "message": "Audit readiness score based on document completeness."
    }
