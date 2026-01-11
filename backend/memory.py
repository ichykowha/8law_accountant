import sqlite3
from datetime import datetime

class AccountingMemory:
    def __init__(self, db_name="accountant_pi.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Initializes the database structure."""
        # Table for Chat History
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_msg TEXT,
                ai_response TEXT
            )
        ''')
        # Table for Financial Records (The 'General Ledger')
        # I added UNIQUE(category) so the update logic below works correctly
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT UNIQUE, 
                value REAL,
                last_updated TEXT
            )
        ''')
        self.conn.commit()

    def save_chat(self, user_msg, ai_response):
        """Saves a conversation turn."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(
            "INSERT INTO chat_history (timestamp, user_msg, ai_response) VALUES (?, ?, ?)",
            (now, user_msg, ai_response)
        )
        self.conn.commit()

    def update_financial(self, category, value):
        """Updates or inserts a financial figure."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Upsert logic: Update if category exists, otherwise insert
        self.cursor.execute('''
            INSERT INTO financial_records (category, value, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(category) DO UPDATE SET value=excluded.value, last_updated=excluded.last_updated
        ''', (category, value, now))
        self.conn.commit()

    def get_recent_history(self, limit=5):
        """Retrieves the last few messages for context."""
        self.cursor.execute("SELECT user_msg, ai_response FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
        return self.cursor.fetchall()
