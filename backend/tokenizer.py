# backend/tokenizer.py
class DataTokenizer:
    def __init__(self):
        pass

    def count_tokens(self, text):
        if not text: return 0
        return len(text) // 4
