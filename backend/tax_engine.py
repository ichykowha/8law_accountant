class TaxEngine:
    def __init__(self):
        # Tax rates by jurisdiction
        self.tax_rates = {
            "UK_VAT": 0.20,
            "US_NY_Sales": 0.08875,
            "EU_Standard": 0.21,
            "GST_AU": 0.10,
            "CA_BC_GST_PST": 0.12 # Added based on your location (Tofino)
        }

    def calculate_tax(self, total_amount, jurisdiction):
        """Extracts tax from a total price."""
        rate = self.tax_rates.get(jurisdiction, 0.0)
        
        # Logic: Total = Net * (1 + Rate)  ->  Net = Total / (1 + Rate)
        net_amount = total_amount / (1 + rate)
        tax_amount = total_amount - net_amount
        
        return {
            "jurisdiction": jurisdiction,
            "net_revenue": round(net_amount, 2),
            "tax_collected": round(tax_amount, 2),
            "rate_used": f"{rate*100}%"
        }