# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Main API Application (FastAPI)
# File: app/main.py
# ------------------------------------------------------------------------------

import sys
import os

# FIX: Add the parent directory to the system path so Python can find 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from fastapi import File, UploadFile
from backend.logic.ocr_engine import scan_pdf
from backend.logic.t4_parser import parse_t4_text

# Import our custom modules
try:
    from backend.database.connection import get_db
    from backend.database.models import User
    from backend.logic.t1_engine import T1DecisionEngine
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    raise e

app = FastAPI(title="8law Super Accountant", version="1.0.0")

# --- Pydantic Models (Data Validation) ---

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str

class TaxCalculationRequest(BaseModel):
    income_type: str  # e.g., "T4", "CAPITAL_GAINS"
    amount: float
    province: str = "ON" # Default to Ontario

# --- API Endpoints ---

@app.get("/")
def health_check():
    """Simple check to see if the server is running."""
    return {"status": "online", "system": "8law-core"}

@app.post("/users/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Creates a new user in the Supabase database."""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create the new user object
    new_user = User(
        email=user.email,
        password_hash=user.password, 
        legal_first_name=user.first_name,
        legal_last_name=user.last_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"status": "success", "user_id": str(new_user.id)}

@app.post("/tax/calculate")
def calculate_tax(request: TaxCalculationRequest):
    """Uses the T1 Decision Engine to calculate tax."""
    engine = T1DecisionEngine(tax_year=2024)
    
    # 1. Process Income Type
    processed = engine.process_income_stream(request.income_type, request.amount)
    
    # 2. Estimate Tax
    taxable_amt = Decimal(processed['taxable_amount'])
    tax_result = engine.calculate_federal_tax(taxable_amt, return_breakdown=True)
    
    return {
        "analysis": processed,
        "tax_estimate": tax_result
    }
@app.post("/document/scan")
async def scan_document(file: UploadFile = File(...)):
    """
    Receives a PDF, scans the text (OCR), AND parses T4 data.
    """
    content = await file.read()
    
    # 1. Get Raw Text (The Eyes)
    ocr_result = scan_pdf(content)
    raw_text = ocr_result.get("raw_text", "")
    
    # 2. Extract Data (The Brain)
    parsed_data = parse_t4_text(raw_text)
    
    return {
        "filename": file.filename,
        "scan_result": ocr_result,
        "parsed_data": parsed_data  # <--- This is the new gold
    }