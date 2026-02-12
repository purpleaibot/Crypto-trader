import time
import logging
import json
import sqlite3
import pandas as pd
import ccxt
import math
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from strategy import Strategy

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HiveEngine")

# Configuration
DB_PATH = "trades.db"
ANALYZE_AGENT_URL = "http://localhost:8000/analyze"

class HiveEngine:
    def __init__(self):
        self.active_instances = {} # {id: config}
        self.fetchers = {} # {exchange_key: DataFetcher}
        self.strategy = Strategy()
        self.next_wake_time = 0
        logger.info("🐝 Hive Engine Initialized")

    def load_instances(self):
        """Load ACTIVE instances from DB"""
        try:
            conn = sqlite3.connect(DB_PATH)
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
                    
                    config = json.loads(row['strategy_config']) if row['strategy_config'] else {}
                    
                    self.active_instances[instance_id] = {
                        "id": row['id'],
                        "name": row['name'],
                        "exchange": row['exchange'],
                        "market_type": row['market_type'],
                        "pairs": json.loads(row['pairs']) if row['pairs'] else [],
                        "config": config,
                        "timeframes": config.get('strategy', {}).get('timeframes', ['1h']) # Default if missing
                    }
                    
                    # Initialize Fetcher (Keyed by Exchange + Type)
                    # e.g. "binance_Futures" vs "binance_Spot"
                    fetcher_key = f"{row['exchange']}_{row['market_type']}"
                    if fetcher_key not in self.fetchers:
                        self.fetchers[fetcher_key] = DataFetcher(
                            exchange_id=row['exchange'], 
                            market_type=row['market_type']
                        )

            # Remove stopped instances
            active_ids = list(self.active_instances.keys())
            for iid in active_ids:
                if iid not in current_ids:
                    logger.info(f"➖ Unloaded Instance: {self.active_instances[iid]['name']}")
                    del self.active_instances[iid]
                    
        except Exception as e:
            logger.error(f"Error loading instances: {e}")

    def get_time_to_next_candle(self, timeframe):
        """
        Calculate seconds remaining until the next candle closes + 5 seconds buffer.
        """
        # Parse timeframe to seconds using CCXT logic manually or helper
        # Simple map for standard TFs
        tf_seconds = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600, '8h': 28800, '12h': 43200,
            '1d': 86400, '1w': 604800
        }
        
        duration = tf_seconds.get(timeframe, 3600)
        
        now_ts = time.time()
        # Find start of current candle
        # Candle start = now // duration * duration
        # Next close = Candle start + duration
        next_close = (int(now_ts) // duration * duration) + duration
        
        wait_seconds = next_close - now_ts + 5 # +5s buffer
        return max(5, wait_seconds) # Wait at least 5s

    def run_cycle(self):
        """Main execution loop with Smart Sleep"""
        self.load_instances()
        
        if not self.active_instances:
            logger.info("💤 No active instances. Waiting 10s...")
            time.sleep(10)
            return

        min_sleep = 3600 # Default cap
        
        logger.info(f"🔄 Cycling through {len(self.active_instances)} instances...")
        
        for iid, instance in self.active_instances.items():
            try:
                # 1. Process
                self.process_instance(instance)
                
                # 2. Determine Sleep Requirement for this instance
                for tf in instance['timeframes']:
                    wait = self.get_time_to_next_candle(tf)
                    if wait < min_sleep:
                        min_sleep = wait
                        
            except Exception as e:
                logger.error(f"Error processing {instance['name']}: {e}")
        
        logger.info(f"✅ Cycle complete. Next wake in {min_sleep:.1f}s")
        time.sleep(min_sleep)

    def process_instance(self, instance):
        """Process a single instance: Fetch -> Analyze -> Signal"""
        fetcher_key = f"{instance['exchange']}_{instance['market_type']}"
        fetcher = self.fetchers.get(fetcher_key)
        if not fetcher: return

        pairs = instance['pairs']
        timeframes = instance['timeframes']
        
        # logger.info(f"[{instance['name']}] Checking {len(pairs)} pairs on {timeframes}...")
        
        for pair_data in pairs:
            symbol = pair_data['Symbol'] if isinstance(pair_data, dict) else pair_data
            
            # Loop through ALL configured timeframes
            data_map = {}
            for tf in timeframes:
                # Fetch 500 candles (default limit in DataFetcher)
                df = fetcher.fetch_ohlcv(symbol, tf, limit=500)
                if df is not None and not df.empty:
                    data_map[tf] = df
            
            # TODO: Pass data_map to Strategy to check multi-timeframe conditions
            # For V1 MVP, we just check the smallest TF or the first one
            if data_map:
                primary_tf = timeframes[0] # Assuming first is "Small TF" or Trigger
                if primary_tf in data_map:
                    df = data_map[primary_tf]
                    
                    # Calculate Indicators
                    df = self.strategy.calculate_indicators(df)
                    
                    # Mock Trend Logic (In future, use larger TF from data_map)
                    trend = "NEUTRAL"
                    
                    signal = self.strategy.check_trigger(df, trend)
                    
                    if signal:
                        logger.info(f"🚀 SIGNAL [{instance['name']}]: {signal} on {symbol} ({primary_tf})")
                        # self.send_to_agent(...)

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
