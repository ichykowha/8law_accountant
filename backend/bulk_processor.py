import pandas as pd
import sqlite3

class BulkProcessor:
    def __init__(self, db_name="accountant_pi.db"):
        self.db_name = db_name

    def ingest_spreadsheet(self, file_path):
        """Reads CSV or Excel and prepares it for the AI."""
        try:
            # Detect file type and load
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            else:
                return "Unsupported file format. Please use .csv or .xlsx."

            # Standardize column names (force lowercase)
            df.columns = [c.lower() for c in df.columns]
            
            # Simple check to ensure we have the columns we need
            if 'category' not in df.columns or 'amount' not in df.columns:
                 return "Error: Spreadsheet must have 'category' and 'amount' columns."
            
            # Send to database
            return self._save_to_ledger(df)
            
        except Exception as e:
            return f"Error processing file: {str(e)}"

    def _save_to_ledger(self, df):
        """Iterates through the spreadsheet and saves to the Memory Module."""
        conn = sqlite3.connect(self.db_name)
        
        count = 0
        for _, row in df.iterrows():
            # Using the same logic as memory.py
            conn.execute('''
                INSERT INTO financial_records (category, value, last_updated) 
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(category) DO UPDATE SET value=excluded.value, last_updated=excluded.last_updated
            ''', (row['category'], row['amount']))
            count += 1
            
        conn.commit()
        conn.close()
        return f"Successfully ingested {count} transactions into the ledger."