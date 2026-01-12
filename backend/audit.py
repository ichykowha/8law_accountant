import hashlib
import json
import time

class Block:
    def __init__(self, index, transaction_data, previous_hash):
        self.index = index
        self.timestamp = time.time()
        self.data = transaction_data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        # We combine all data into a string and hash it
        block_string = json.dumps(self.data, sort_keys=True) + str(self.index) + str(self.timestamp) + self.previous_hash
        return hashlib.sha256(block_string.encode()).hexdigest()

class AuditTrail:
    def __init__(self):
        # The "Genesis Block" starts the chain
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "Genesis Block - Ledger Started", "0")

    def create_entry(self, action, details):
        previous_block = self.chain[-1]
        data = {"action": action, "details": details}
        
        new_block = Block(len(self.chain), data, previous_block.hash)
        self.chain.append(new_block)
        return new_block.hash

    def is_chain_valid(self):
        """Verifies that no one has tampered with the ledger."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            
            # Check 1: Did the data change? (Hash mismatch)
            if current.hash != current.calculate_hash():
                return False
            # Check 2: Did the link break?
            if current.previous_hash != previous.hash:
                return False
        return True