import math

class MathEngine:
    def __init__(self):
        pass

    def calculate_interest(self, principal, rate, time):
        """Simple Interest Formula: P * R * T"""
        return (principal * rate * time) / 100

    def compound_interest(self, principal, rate, times_per_year, years):
        """Compound Interest Formula"""
        amount = principal * (1 + (rate / (times_per_year * 100))) ** (times_per_year * years)
        return round(amount - principal, 2)