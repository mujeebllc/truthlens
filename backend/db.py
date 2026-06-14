import os
import sqlite3
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truthlens.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create claims table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_text TEXT NOT NULL,
        verdict TEXT NOT NULL,
        score INTEGER NOT NULL,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create source reputation table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_reputation (
        domain TEXT PRIMARY KEY,
        reliability_score INTEGER NOT NULL
    )
    """)
    
    # Create feedback table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id INTEGER,
        user_vote TEXT NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (claim_id) REFERENCES claims(id)
    )
    """)
    
    conn.commit()
    
    # Seed source reputation if empty
    cursor.execute("SELECT COUNT(*) FROM source_reputation")
    count = cursor.fetchone()[0]
    if count == 0:
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "source_reputation_seed.json")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                seeds = json.load(f)
                for entry in seeds:
                    cursor.execute(
                        "INSERT OR IGNORE INTO source_reputation (domain, reliability_score) VALUES (?, ?)",
                        (entry["domain"], entry["reliability_score"])
                    )
            conn.commit()
            print("Successfully seeded source_reputation table.")
        else:
            print(f"Warning: Seed file not found at {seed_path}")
            
    conn.close()

if __name__ == "__main__":
    init_db()
