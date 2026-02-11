import sqlite3
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger("DBManager")

class DBManager:
    def __init__(self, db_path=None):
        # Default to /data volume if in Docker, else local file
        if db_path is None:
            if os.path.exists("/data"):
                self.db_path = "/data/trades.db"
            else:
                self.db_path = "trades.db"
        else:
            self.db_path = db_path
            
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                amount REAL,
                entry_price REAL,
                status TEXT, -- OPEN, CLOSED, REJECTED
                pnl REAL DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                agent_notes TEXT,
                user_grade TEXT
            )
        ''')
        
        # Instance State Table (Capital & Levels)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instance_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_capital REAL,
                current_level TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def log_trade(self, trade_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (symbol, side, amount, entry_price, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (trade_data['symbol'], trade_data['side'], trade_data['amount'], trade_data['price'], 'OPEN'))
        conn.commit()
        conn.close()
        logger.info(f"Trade logged: {trade_data['symbol']}")

    def update_capital(self, capital, level):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO instance_state (total_capital, current_level) VALUES (?, ?)', (capital, level))
        conn.commit()
        conn.close()

    def get_trades(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
