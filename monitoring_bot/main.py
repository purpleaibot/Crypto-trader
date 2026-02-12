import time
import logging
import json
import sqlite3
import pandas as pd
import asyncio
import concurrent.futures
from data_fetcher import DataFetcher
from strategy import Strategy
from datetime import datetime

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HiveEngine")

# Configuration
DB_PATH = "trades.db"
ANALYZE_AGENT_URL = "http://localhost:8000/analyze"

class HiveEngine:
    def __init__(self):
        self.active_instances = {} # {id: config}
        self.fetchers = {} # {exchange: DataFetcher}
        self.strategy = Strategy()
        logger.info("🐝 Hive Engine Initialized")

    def load_instances(self):
        """Load ACTIVE instances from DB"""
        try:
            conn = sqlite3.connect(DB_PATH)
            # Create table if missing (safety check)
            conn.execute('''CREATE TABLE IF NOT EXISTS instances (
                id TEXT PRIMARY KEY, name TEXT, exchange TEXT, base_currency TEXT, 
                market_type TEXT, strategy_config TEXT, pairs TEXT, 
                status TEXT DEFAULT 'STOPPED', created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            df = pd.read_sql("SELECT * FROM instances WHERE status='ACTIVE'", conn)
            conn.close()
            
            current_ids = set()
            for _, row in df.iterrows():
                instance_id = row['id']
                current_ids.add(instance_id)
                
                # Register new or update existing
                if instance_id not in self.active_instances:
                    logger.info(f"➕ Loaded Instance: {row['name']} ({row['exchange']})")
                    self.active_instances[instance_id] = {
                        "id": row['id'],
                        "name": row['name'],
                        "exchange": row['exchange'],
                        "pairs": json.loads(row['pairs']) if row['pairs'] else [],
                        "config": json.loads(row['strategy_config']) if row['strategy_config'] else {}
                    }
                    
                    # Initialize Fetcher for this exchange if needed
                    if row['exchange'] not in self.fetchers:
                        self.fetchers[row['exchange']] = DataFetcher(exchange_id=row['exchange'])

            # Remove stopped instances
            active_ids = list(self.active_instances.keys())
            for iid in active_ids:
                if iid not in current_ids:
                    logger.info(f"➖ Unloaded Instance: {self.active_instances[iid]['name']}")
                    del self.active_instances[iid]
                    
        except Exception as e:
            logger.error(f"Error loading instances: {e}")

    def run_cycle(self):
        """Main execution loop"""
        self.load_instances()
        
        if not self.active_instances:
            logger.info("💤 No active instances. Waiting...")
            time.sleep(10)
            return

        logger.info(f"🔄 Cycling through {len(self.active_instances)} instances...")
        
        for iid, instance in self.active_instances.items():
            try:
                self.process_instance(instance)
            except Exception as e:
                logger.error(f"Error processing {instance['name']}: {e}")
        
        logger.info("✅ Cycle complete. Sleeping...")
        time.sleep(60) # Main heartbeat

    def process_instance(self, instance):
        """Process a single instance: Fetch -> Analyze -> Signal"""
        exchange = instance['exchange']
        fetcher = self.fetchers.get(exchange)
        if not fetcher: return

        pairs = instance['pairs']
        # Limit processing for now to avoid overloading
        # In V2, we batch this via Async
        
        logger.info(f"[{instance['name']}] Checking {len(pairs)} pairs...")
        
        for pair_data in pairs:
            # pair_data structure from dashboard might be a dict or string
            symbol = pair_data['Symbol'] if isinstance(pair_data, dict) else pair_data
            
            # 1. Fetch Data (Optimized: Just 1H for trigger check for now)
            # In real PROD, fetcher should support bulk fetch
            df_1h = fetcher.fetch_ohlcv(symbol, "1h", limit=50)
            
            if df_1h is not None and not df_1h.empty:
                # 2. Strategy Check
                df_1h = self.strategy.calculate_indicators(df_1h)
                
                # Mock Trend (Needs 4H/1D in full version)
                trend = "NEUTRAL" 
                
                signal = self.strategy.check_trigger(df_1h, trend)
                
                if signal:
                    logger.info(f"🚀 SIGNAL [{instance['name']}]: {signal} on {symbol}")
                    # TODO: Send to Analyze Agent with instance_id
                    # self.send_to_agent(instance['id'], symbol, signal, ...)

if __name__ == "__main__":
    engine = HiveEngine()
    while True:
        try:
            engine.run_cycle()
        except KeyboardInterrupt:
            logger.info("Hive Engine Stopped.")
            break
        except Exception as e:
            logger.critical(f"Hive Crash: {e}")
            time.sleep(10)
