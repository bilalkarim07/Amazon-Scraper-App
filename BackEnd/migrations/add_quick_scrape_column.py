""" add_quick_scrape_column.py — Migration script for adding the quick_scrape column. """

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(jobs)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "quick_scrape" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN quick_scrape INTEGER DEFAULT 0")
        conn.commit()
        print("✓ Added 'quick_scrape' column.")
    else:
        print("✓ 'quick_scrape' column already exists.")
    conn.close()

if __name__ == "__main__":
    migrate()