# controller.py - The Super Accountant Controller

import sys
import os

# Path setup
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Import all engines
from backend.ai_brain import AccountingBrain
from backend.math_engine import MathEngine
from backend.tokenizer import DataTokenizer
from backend.memory import AccountingMemory
from backend.error_handler import ErrorHandler
from backend.visualizer import FinancialVisualizer
from backend.ingestor import UniversalIngestor 
from backend.tax_engine import TaxEngine       
from backend.audit import AuditTrail           
from backend.reporting import ReportingEngine  
from backend.forecaster import BalanceForecaster 
from backend.query_engine import DataQueryAssistant # NEW

class PowerhouseAccountant:
    def __init__(self):
        # Initialize backend components
        self.memory = AccountingMemory()
        self.brain = AccountingBrain()       
        self.math = MathEngine()             
        self.tokenizer = DataTokenizer()     
        self.handler = ErrorHandler()       
        self.visualizer = FinancialVisualizer()
        self.ingestor = UniversalIngestor(self.memory)
        self.tax_engine = TaxEngine()
        self.audit = AuditTrail()
        self.reporter = ReportingEngine(self.memory)
        self.forecaster = BalanceForecaster()
        self.query_engine = DataQueryAssistant() # NEW
        
    def process_input(self, user_text):
        # 1. Handle Pending Tasks
        if self.handler.pending_task:
            return self.continue_pending_task(user_text)

        # 2. Detect Intent
        intent = self.detect_intent(user_text)

        # 3. Routing Logic
        if intent == "QUERY_DATA":
            return self.query_engine.ask(user_text)

        elif intent == "FORECAST":
            data = self.forecaster.project_balance(30)
            return f"Projection (30 Days): Current ${data['current_balance']} -> Future ${data['projected_balance']}. Status: {data['status']}"

        elif intent == "REPORT":
            return self.reporter.generate_p_and_l()
            
        elif intent == "VISUALIZE":
            status = self.visualizer.plot_revenue_vs_expenses()
            return f"Chart updated. {status}"

        elif intent == "MATH":
            if "tax" in user_text.lower():
                res = self.tax_engine.calculate_tax(1000, "CA_BC_GST_PST")
                return f"Tax Calculation (BC Example): On $1000, Net is ${res['net_revenue']}, Tax is ${res['tax_collected']}"
            else:
                return "I can calculate taxes or interest. Please specify."
        
        elif intent == "INGEST":
            return "To ingest data, please drag and drop a file in the sidebar."

        # Default Chat
        self.memory.save_chat(user_text, "Processed")
        return "I'm listening. Ask me about your spending, forecasts, or upload a receipt."

    def detect_intent(self, text):
        text = text.lower()
        if any(w in text for w in ["spent", "cost", "how much", "total for"]): return "QUERY_DATA"
        if any(w in text for w in ["future", "predict", "forecast", "runway", "cash flow"]): return "FORECAST"
        if any(w in text for w in ["report", "p&l", "balance sheet", "statement"]): return "REPORT"
        if any(w in text for w in ["chart", "graph", "visual"]): return "VISUALIZE"
        if any(w in text for w in ["calculate", "math", "interest", "tax"]): return "MATH"
        if any(w in text for w in ["scan", "read", "ingest", "upload"]): return "INGEST"
        return "CHAT"

    def continue_pending_task(self, user_text):
        self.handler.pending_task = None 
        return "Task reset. How else can I help?"