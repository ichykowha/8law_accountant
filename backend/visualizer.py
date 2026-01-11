import matplotlib.pyplot as plt
import sqlite3
import os

class FinancialVisualizer:
    def __init__(self, db_name="accountant_pi.db"):
        self.db_name = db_name

    def plot_revenue_vs_expenses(self):
        """Generates a bar chart comparing total revenue and expenses."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Fetch data from our Memory Module
        cursor.execute("SELECT category, value FROM financial_records WHERE category IN ('Revenue', 'Expense')")
        data = cursor.fetchall()
        conn.close()

        if not data:
            return "No financial data found to visualize."

        categories = [row[0] for row in data]
        values = [row[1] for row in data]

        # Create the plot
        plt.figure(figsize=(8, 5))
        colors = ['#4CAF50', '#F44336'] # Green for revenue, Red for expense
        # Ensure we have enough colors if there are many categories
        if len(categories) > 2:
            colors = colors * (len(categories) // 2 + 1)
            
        plt.bar(categories, values, color=colors[:len(categories)])
        
        plt.title('Financial Health Overview')
        plt.ylabel('Amount ($)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Save the report in the app folder so the UI can see it later
        # We save it to the current directory
        file_name = "financial_report.png"
        plt.savefig(file_name)
        plt.close()
        
        return f"Report generated successfully! Saved as {file_name}."