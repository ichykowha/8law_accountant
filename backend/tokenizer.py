import torch

class DataTokenizer:
    def __init__(self, vocab_size=1000):
        # A simple dictionary to map common accounting words to unique IDs
        self.vocab = {
            "<PAD>": 0, "tax": 1, "revenue": 2, "expense": 3,
            "audit": 4, "profit": 5, "loss": 6, "invoice": 7,
            "interest": 8, "liability": 9, "asset": 10,
            "calculate": 11, "help": 12  # Added for chat context
        }
        self.reverse_vocab = {v: k for k, v in self.vocab.items()}

    def tokenize_text(self, text):
        """Converts a sentence into a list of numerical IDs."""
        words = text.lower().replace(".", "").replace("?", "").split()
        # 0 if word is unknown
        tokens = [self.vocab.get(w, 0) for w in words] 
        
        # Convert to a PyTorch Tensor for the Neural Network
        return torch.tensor(tokens, dtype=torch.long)

    def normalize_financials(self, value, max_val=1000000):
        """
        Scales large currency numbers between 0 and 1.
        Neural networks perform much better with small decimal ranges.
        """
        scaled = value / max_val
        return torch.tensor([scaled], dtype=torch.float32)

    def de_tokenize(self, tensor):
        """Converts IDs back into human-readable words."""
        # Handle single integer or tensor input
        if isinstance(tensor, int):
            return self.reverse_vocab.get(tensor, "???")
        return " ".join([self.reverse_vocab.get(int(i), "???") for i in tensor])