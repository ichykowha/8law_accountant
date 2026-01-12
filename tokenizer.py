# backend/tokenizer.py - Lightweight Version

class DataTokenizer:
    def __init__(self):
        pass

    def count_tokens(self, text):
        # Simple estimation (4 chars ~= 1 token) instead of loading heavy libraries
        if not text:
            return 0
        return len(text) // 4