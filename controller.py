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
from backend.query_engine import DataQueryAssistant 

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
        self.query_engine = DataQueryAssistant()
        
    def process_input(self, user_text):
        # 1. Handle Pending Tasks
        if self.handler.pending_task:
            return self.continue_pending_task(user_text)

        # 2. Detect Specific Actions (Charts, Uploads)
        intent = self.detect_intent(user_text)

        if intent == "FORECAST":
            data = self.forecaster.project_balance(30)
            return f"Projection (30 Days): Current ${data['current_balance']} -> Future ${data['projected_balance']}. Status: {data['status']}"

        elif intent == "REPORT":
            return self.reporter.generate_p_and_l()
            
        elif intent == "VISUALIZE":
            status = self.visualizer.plot_revenue_vs_expenses()
            return f"Chart updated. {status}"

        elif intent == "INGEST":
            return "To ingest data, please drag and drop a file in the sidebar."

        # 3. THE UPGRADE: "Chat with Data" (Default Fallback)
        # If we don't know what to do, we ask the AI Brain.
        
        # We use the query engine we built. It returns a dictionary {answer, reasoning}
        # We just want the answer string for the simple chat window.
        ai_result = self.query_engine.ask(user_text)
        
        # Save to memory
        self.memory.save_chat(user_text, ai_result['answer'])
        
        return ai_result['answer']

    def detect_intent(self, text):
        text = text.lower()
        # I removed "QUERY_DATA" and "MATH" from here because we want those 
        # to fall through to the AI Brain (Step 3) automatically.
        if any(w in text for w in ["future", "predict", "runway", "cash flow"]): return "FORECAST"
        if any(w in text for w in ["report", "p&l", "balance sheet"]): return "REPORT"
        if any(w in text for w in ["chart", "graph", "visual"]): return "VISUALIZE"
        if any(w in text for w in ["scan", "ingest", "upload"]): return "INGEST"
        return "CHAT" # Falls through to AI

    def continue_pending_task(self, user_text):
        self.handler.pending_task = None 
        return "Task reset. How else can I help?"
