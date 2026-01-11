import math

class MathEngine:
    def __init__(self):
        print("Mathematical Engine Online.")

    # --- BASIC MATH ---
    def add(self, *args):
        return sum(args)

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            return "Error: Division by zero"
        return a / b

    # --- ADVANCED ACCOUNTING MATH ---
    def calculate_compound_interest(self, principal, rate, time, n=12):
        """
        Calculates: A = P(1 + r/n)^(nt)
        P = principal, r = annual interest rate, t = years, n = times compounded/year
        """
        amount = principal * (1 + (rate / n))**(n * time)
        interest = amount - principal
        return {"total_balance": round(amount, 2), "interest_earned": round(interest, 2)}

    def calculate_tax(self, income, brackets):
        """
        Calculates progressive tax based on a dictionary of brackets.
        Example brackets: {10000: 0.10, 40000: 0.15, 90000: 0.25}
        """
        tax = 0
        previous_limit = 0
        # Sort brackets to ensure we calculate in order
        for limit, rate in sorted(brackets.items()):
            if income > limit:
                tax += (limit - previous_limit) * rate
                previous_limit = limit
            else:
                tax += (income - previous_limit) * rate
                return round(tax, 2)
        # If income exceeds all brackets, tax the remainder at the highest rate
        tax += (income - previous_limit) * list(sorted(brackets.items()))[-1][1]
        return round(tax, 2)

    def net_present_value(self, rate, cash_flows):
        """
        Calculates the NPV of an investment.
        rate: discount rate (0.05 for 5%)
        cash_flows: list of flows starting at year 0
        """
        npv = sum(cf / (1 + rate)**i for i, cf in enumerate(cash_flows))
        return round(npv, 2)