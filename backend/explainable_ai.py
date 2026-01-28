# backend/explainable_ai.py
"""
Explainable AI utilities for 8law: show reasoning and confidence for AI/ML outputs.
"""
def explain_classification(doc_text, label, confidence):
    # Placeholder: simple explanation
    return {
        "label": label,
        "confidence": confidence,
        "reasoning": f"Classified as '{label}' with confidence {confidence*100:.1f}% based on keyword analysis."
    }

def explain_anomaly(transaction, reason):
    return {
        "transaction": transaction,
        "reason": reason,
        "explanation": f"Flagged as anomaly because: {reason}"
    }
