import json
import os
from datetime import datetime

class AccountingMemory:
    def __init__(self, db_path="chat_history.json"):
        # We are using a JSON file now instead of SQLite
        self.db_path = os.path.join(os.path.dirname(__file__), db_path)
        self._initialize_file()

    def _initialize_file(self):
        """Creates the history file if it doesn't exist."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w') as f:
                json.dump([], f)

    def save_chat(self, user_input, system_response):
        """Saves a conversation pair to the JSON log."""
        entry = {
            "timestamp": str(datetime.now()),
            "user": user_input,
            "assistant": system_response
        }
        
        try:
            # 1. Read existing history
            with open(self.db_path, 'r') as f:
                history = json.load(f)
            
            # 2. Add new entry
            history.append(entry)
            
            # 3. Save back to file
            with open(self.db_path, 'w') as f:
                json.dump(history, f, indent=4)
                
        except Exception as e:
            print(f"Error logging chat: {e}")

    def get_recent_context(self, limit=5):
        """Retrieves the last few messages for context."""
        try:
            with open(self.db_path, 'r') as f:
                history = json.load(f)
            return history[-limit:]
        except:
            return []