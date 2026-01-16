
-- ------------------------------------------------------------------------------
-- 8law - Super Accountant
-- Module: Database Schema (PostgreSQL)
-- File: backend/database/schema.sql
-- ------------------------------------------------------------------------------

-- Enable UUID extension for secure, non-guessable IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS TABLE
-- The humans (or companies) using 8law.
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- Never store raw passwords!
    legal_first_name VARCHAR(100),
    legal_last_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. TAX RETURNS
-- A "Folder" for a specific tax year (e.g., Matt's 2024 Return).
CREATE TABLE tax_returns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tax_year INT NOT NULL,
    province VARCHAR(2) NOT NULL, -- ON, BC, AB, etc.
    status VARCHAR(50) DEFAULT 'DRAFT', -- DRAFT, REVIEW, FILED
    
    -- Financial Snapshot (Calculated by T1 Engine)
    total_income DECIMAL(15, 2) DEFAULT 0.00,
    taxable_income DECIMAL(15, 2) DEFAULT 0.00,
    total_tax_payable DECIMAL(15, 2) DEFAULT 0.00,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. NOTICE OF ASSESSMENTS (NOA)
-- This stores the critical data from the "Last Year" PDF upload.
-- Your T1 Engine reads this to authorize RRSP contributions.
CREATE TABLE notice_of_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tax_year INT NOT NULL, -- The year the NOA is FOR (usually previous year)
    
    -- The "Golden Numbers" from CRA
    rrsp_deduction_limit DECIMAL(15, 2) NOT NULL,
    unused_rrsp_contributions DECIMAL(15, 2) DEFAULT 0.00,
    
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. INCOME SLIPS (The Raw Data)
-- Stores every T4, T5, or Receipt uploaded.
CREATE TABLE income_slips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tax_return_id UUID REFERENCES tax_returns(id) ON DELETE CASCADE,
    
    slip_type VARCHAR(20) NOT NULL, -- T4, T5, T5008, RECEIPT
    issuer_name VARCHAR(255), -- Employer Name or Bank Name
    
    -- We store the full JSON data extracted by OCR.
    -- This allows us to store Box 14, Box 22, etc., without needing 
    -- a dedicated column for every possible tax box.
    raw_data JSONB NOT NULL, 
    
    -- The specific amount we pulled for tax calc (Audit Trail)
    taxable_amount_extracted DECIMAL(15, 2) NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. AUDIT LOG (Immutable)
-- Every time the AI makes a decision, we log it here.
-- This is what eventually gets hashed to the Blockchain.
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tax_return_id UUID REFERENCES tax_returns(id),
    action VARCHAR(255) NOT NULL, -- e.g., "Applied 50% Cap Gains Inclusion"
    details TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- 6. IMMUTABLE LEDGER (The Internal Blockchain)
-- This table stores the cryptographic "Seals" for every tax return.
-- If anyone alters the 'tax_returns' table, the hashes here will fail to match,
-- triggering a security alert.

CREATE TABLE blockchain_ledger (
    block_id SERIAL PRIMARY KEY, -- 1, 2, 3 (The height of the chain)
    
    -- The "Payload" we are sealing (e.g., The UUID of the Tax Return)
    entity_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- 'TAX_RETURN', 'NOA'
    
    -- The Digital Fingerprint of the data at that moment
    data_hash VARCHAR(64) NOT NULL, -- SHA-256 Hash
    
    -- The Link to the Previous Block (The Chain)
    previous_block_hash VARCHAR(64) NOT NULL,
    
    -- The Timestamp and Nonce (for uniqueness)
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    nonce VARCHAR(32),
    
    -- Final "Seal" of this block (Hash of current data + previous hash)
    block_hash VARCHAR(64) NOT NULL UNIQUE
);

-- Index for speed verification
CREATE INDEX idx_chain_order ON blockchain_ledger(block_id);
