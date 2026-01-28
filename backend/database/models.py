# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Database Models (ORM)
# File: backend/database/models.py
# ------------------------------------------------------------------------------

from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey, DateTime, JSON, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)

    password_hash = Column(String, nullable=False)
    legal_first_name = Column(String, nullable=True)
    legal_last_name = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    tax_returns = relationship("TaxReturn", back_populates="user")
    noas = relationship("NoticeOfAssessment", back_populates="user")


class NoticeOfAssessment(Base):
    """
    Maps to the 'notice_of_assessments' table.
    This holds the data your T1 Engine needs for RRSP logic.
    """
    __tablename__ = 'notice_of_assessments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    tax_year = Column(Integer, nullable=False)
    
    # The Critical Numbers
    rrsp_deduction_limit = Column(DECIMAL(15, 2), nullable=False)
    unused_rrsp_contributions = Column(DECIMAL(15, 2), default=0)
    
    user = relationship("User", back_populates="noas")

class TaxReturn(Base):
    __tablename__ = 'tax_returns'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    tax_year = Column(Integer, nullable=False)
    province = Column(String(2), nullable=False)
    
    # Calculated Fields (from T1 Engine)
    total_tax_payable = Column(DECIMAL(15, 2), default=0)
    
    user = relationship("User", back_populates="tax_returns")
    slips = relationship("IncomeSlip", back_populates="tax_return")

class IncomeSlip(Base):
    """
    Stores the raw data from OCR so we can prove where the numbers came from.
    """
    __tablename__ = 'income_slips'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_return_id = Column(UUID(as_uuid=True), ForeignKey('tax_returns.id'))
    
    slip_type = Column(String, nullable=False) # T4, T5, etc.
    raw_data = Column(JSON, nullable=False)    # {"box14": 50000, "box22": 10000}
    
    tax_return = relationship("TaxReturn", back_populates="slips")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    amount = Column(Float, nullable=False)
    description = Column(String)
    category = Column(String)
    vendor = Column(String)
    source = Column(String)  # e.g., 'bank', 'receipt', 'manual'
    status = Column(String, default="pending")  # e.g., 'pending', 'reviewed', 'reconciled'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("User", backref="transactions")
