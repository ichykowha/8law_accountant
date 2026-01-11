class ReportingEngine:
    def __init__(self, memory_module):
        self.memory = memory_module

    def generate_p_and_l(self):
        """Generates a text-based P&L Statement."""
        # Fetch all data
        conn = self.memory.conn
        cursor = conn.cursor()
        cursor.execute("SELECT category, value FROM financial_records")
        data = cursor.fetchall()
        
        # Simple Logic to split Revenue vs Expense
        # In a real app, we'd have a 'type' column, but here we guess by name
        revenue = 0.0
        expenses = 0.0
        
        details = ""
        
        for category, value in data:
            cat_lower = category.lower()
            if "revenue" in cat_lower or "sales" in cat_lower or "income" in cat_lower:
                revenue += value
                details += f"  + {category}: ${value}\n"
            else:
                expenses += value
                details += f"  - {category}: ${value}\n"
                
        net_income = revenue - expenses
        
        report = f"""
        === PROFIT & LOSS STATEMENT ===
        Total Revenue:  ${round(revenue, 2)}
        Total Expenses: ${round(expenses, 2)}
        -------------------------------
        NET INCOME:     ${round(net_income, 2)}
        ===============================
        
        Details:
        {details}
        """
        return report