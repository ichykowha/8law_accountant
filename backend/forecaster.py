import sqlite3
from datetime import datetime, timedelta

class BalanceForecaster:
    def __init__(self, db_name="accountant_pi.db"):
        self.db_name = db_name

    def project_balance(self, days_ahead=30):
        """Calculates Burn Rate and projects future liquidity."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # 1. Get Totals
        cursor.execute("SELECT category, value FROM financial_records")
        data = cursor.fetchall()
        conn.close()

        total_revenue = sum(row[1] for row in data if "Revenue" in row[0])
        total_expense = sum(row[1] for row in data if "Expense" in row[0])
        current_cash = total_revenue - total_expense

        # 2. Simple Daily Average Logic (Demo Version)
        # In a real app, we would check dates. Here we assume history is over 30 days.
        assumed_history_days = 30 
        
        daily_revenue = total_revenue / assumed_history_days
        daily_expense = total_expense / assumed_history_days
        net_daily = daily_revenue - daily_expense

        # 3. Project Forward
        projected_balance = current_cash + (net_daily * days_ahead)
        
        # 4. Runway Warning
        status = "Healthy"
        if projected_balance < 0:
            status = "DANGER: Negative Cash Flow Predicted"
        elif projected_balance < current_cash:
            status = "Warning: Burning Cash"

        return {
            "current_balance": round(current_cash, 2),
            "projected_balance": round(projected_balance, 2),
            "days_ahead": days_ahead,
            "status": status
        }