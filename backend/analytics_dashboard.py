# backend/analytics_dashboard.py
"""
Advanced analytics dashboard for 8law (scaffold).
"""
def get_trends(transactions):
    # Placeholder: return dummy trend data
    return {
        "monthly_expenses": [1000, 1200, 1100, 1300, 1250],
        "monthly_income": [5000, 5200, 5100, 5300, 5250]
    }

def get_risk_insights(transactions):
    # Placeholder: flag months with high expenses
    return [i for i, v in enumerate(get_trends(transactions)["monthly_expenses"]) if v > 1250]
