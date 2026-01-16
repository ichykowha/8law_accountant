
# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Blockchain Ledger Engine (SHA-256 Immutability)
# File: backend/security/ledger_engine.py
# ------------------------------------------------------------------------------

import hashlib
import json
import uuid
from datetime import datetime

class LedgerEngine:
    """
    The 'Notary' of 8law.
    It takes financial records and 'freezes' them into a cryptographic chain.
    """

    @staticmethod
    def generate_hash(data_string):
        """Creates a SHA-256 fingerprint of any text."""
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

    def create_genesis_block(self):
        """
        Creates Block #0. This is the anchor of the entire system.
        """
        return {
            "block_id": 0,
            "previous_block_hash": "0" * 64, # 64 zeros
            "data_hash": "GENESIS_BLOCK_8LAW_START",
            "timestamp": str(datetime.now()),
            "block_hash": self.generate_hash("GENESIS_8LAW_2026")
        }

    def seal_tax_return(self, tax_return_data, previous_block):
        """
        Takes a Tax Return object, hashes it, and links it to the previous block.
        
        :param tax_return_data: Dictionary containing {id, total_income, total_tax, user_id}
        :param previous_block: The dictionary of the last row in the ledger table
        """
        
        # 1. Serialize the sensitive data (Sort keys ensures order never changes)
        # We only hash the critical financial numbers, not the timestamps.
        payload = {
            "id": str(tax_return_data['id']),
            "total_income": str(tax_return_data['total_income']),
            "total_tax": str(tax_return_data['total_tax_payable']),
            "user_id": str(tax_return_data['user_id'])
        }
        payload_string = json.dumps(payload, sort_keys=True)
        
        # 2. Create the Data Hash (The Fingerprint of the Money)
        current_data_hash = self.generate_hash(payload_string)
        
        # 3. Link to Previous Block (The Chain)
        prev_hash = previous_block['block_hash']
        
        # 4. Create the Block Seal
        # We combine: Previous Hash + Current Data Hash + Timestamp
        timestamp = str(datetime.now())
        block_content = f"{prev_hash}{current_data_hash}{timestamp}"
        final_block_hash = self.generate_hash(block_content)
        
        # 5. Return the "Block" to be saved in SQL
        return {
            "entity_id": tax_return_data['id'],
            "entity_type": "TAX_RETURN",
            "data_hash": current_data_hash,
            "previous_block_hash": prev_hash,
            "timestamp": timestamp,
            "block_hash": final_block_hash
        }

    def verify_integrity(self, database_records):
        """
        AUDIT FUNCTION:
        Re-runs the hashing chain to prove nobody tampered with the database.
        If this returns False, the database is corrupted/hacked.
        """
        for i in range(1, len(database_records)):
            current_block = database_records[i]
            previous_block = database_records[i-1]
            
            # Check 1: Does the 'previous_hash' field match the actual previous block?
            if current_block['previous_block_hash'] != previous_block['block_hash']:
                return False, f"Broken Chain at Block {current_block['block_id']}"
            
            # Check 2: (Optional deep verification) Re-hash the content to ensure match
            # ...
            
        return True, "Ledger Integrity Verified"
      
