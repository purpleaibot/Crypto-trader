import time
import logging
import json
import sqlite3
import pandas as pd
import ccxt
import math
import re
from datetime import datetime, timedelta, timezone
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
        self.next_wake_times = {} # {instance_id: next_wake_timestamp}
        logger.info("🐝 Hive Engine Initialized")

    def load_instances(self):
        """Load ACTIVE instances from DB and handle DELETED ones"""
        try:
            conn = sqlite3.connect(DB_PATH)
            # Ensure table exists
            conn.execute('''CREATE TABLE IF NOT EXISTS instances (
                id TEXT PRIMARY KEY, name TEXT, exchange TEXT, base_currency TEXT, 
                market_type TEXT, strategy_config TEXT, pairs TEXT, 
                status TEXT DEFAULT 'STOPPED', created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # 1. Handle DELETED instances first
            deleted_df = pd.read_sql("SELECT * FROM instances WHERE status='DELETED'", conn)
            for _, row in deleted_df.iterrows():
                iid = row['id']
                logger.info(f"🗑️ Cleaning up DELETED instance: {row['name']} ({iid})")
                
                # Unload from memory
                if iid in self.active_instances:
                    del self.active_instances[iid]
                if iid in self.next_wake_times:
                    del self.next_wake_times[iid]
                
                # Cleanup database data (candles) tied to THIS instance_id
                self.cleanup_instance_data(iid)
                
                # Permanently remove from instances table
                conn.execute("DELETE FROM instances WHERE id=?", (iid,))
                conn.commit()

            # 2. Load ACTIVE instances
            df = pd.read_sql("SELECT * FROM instances WHERE status='ACTIVE'", conn)
            conn.close()
            
            current_ids = set()
            for _, row in df.iterrows():
                instance_id = row['id']
                current_ids.add(instance_id)
                
                if instance_id not in self.active_instances:
                    logger.info(f"➕ Loaded Instance: {row['name']} ({row['exchange']})")
                    
                    config = json.loads(row['strategy_config']) if row['strategy_config'] else {}
                    instance_data = {
                        "id": row['id'],
                        "name": row['name'],
                        "exchange": row['exchange'],
                        "market_type": row['market_type'],
                        "pairs": json.loads(row['pairs']) if row['pairs'] else [],
                        "config": config,
                        "timeframes": config.get('timeframes', ['1h'])
                    }
                    self.active_instances[instance_id] = instance_data
                    
                    fetcher_key = f"{row['exchange']}_{row['market_type']}"
                    if fetcher_key not in self.fetchers:
                        self.fetchers[fetcher_key] = DataFetcher(
                            exchange_id=row['exchange'], 
                            market_type=row['market_type']
                        )

            active_ids = list(self.active_instances.keys())
            for iid in active_ids:
                if iid not in current_ids:
                    logger.info(f"➖ Unloaded Instance: {self.active_instances[iid]['name']}")
                    del self.active_instances[iid]
                    if iid in self.next_wake_times:
                        del self.next_wake_times[iid]
                    
        except Exception as e:
            logger.error(f"Error loading instances: {e}")

    def get_next_event_time(self):
        """
        Calculate the earliest time any active instance needs to run a cycle.
        """
        if not self.active_instances:
            return time.time() + 10 # Default wait if no instances

        min_wait = float('inf')
        for iid in list(self.active_instances.keys()):
            if iid not in self.next_wake_times:
                # First time, force immediate run
                return time.time()
            
            min_wait = min(min_wait, self.next_wake_times[iid])
        
        return min_wait

    def run_cycle(self):
        """Main execution loop with Smart Sleep"""
        self.load_instances()
        
        if not self.active_instances:
            logger.info("💤 No active instances. Waiting 10s...")
            time.sleep(10)
            return

        logger.info(f"🔄 Processing {len(self.active_instances)} instances...")
        
        # Process instances that are due (or force first run)
        current_time = time.time()
        for iid, instance in list(self.active_instances.items()):
            needs_processing = False

            # Force processing if never run before or due
            if iid not in self.next_wake_times or self.next_wake_times[iid] <= current_time:
                needs_processing = True

            if needs_processing:
                try:
                    self.process_instance(instance)
                    
                    # Recalculate next wake time after processing
                    # Use the shortest timeframe for the next check
                    instance_min_wait = float('inf')
                    for tf in instance['timeframes']:
                        wait_seconds = self.get_time_to_next_candle(tf)
                        instance_min_wait = min(instance_min_wait, wait_seconds)
                    
                    self.next_wake_times[iid] = time.time() + instance_min_wait
                    logger.info(f"⏰ Next check for {instance['name']} in {instance_min_wait:.1f}s")
                except Exception as e:
                    logger.error(f"Error processing {instance['name']}: {e}", exc_info=True)

        # Final check: sleep until the earliest next event
        current_time = time.time()
        next_event_time = self.get_next_event_time()
        
        if current_time < next_event_time:
            sleep_duration = next_event_time - current_time
            logger.info(f"✅ Cycle complete. Waiting {sleep_duration:.1f}s for next event.")
            time.sleep(sleep_duration)

    def process_instance(self, instance):
        """Process a single instance: Fetch -> Analyze -> Signal"""
        fetcher_key = f"{instance['exchange']}_{instance['market_type']}"
        fetcher = self.fetchers.get(fetcher_key)
        if not fetcher: 
            logger.warning(f"Fetcher not found for {fetcher_key}. Skipping instance {instance['name']}.")
            return

        pairs = instance['pairs']
        timeframes = instance['timeframes']
        instance_id = instance['id']
        
        logger.info(f"[{instance['name']}] Checking {len(pairs)} pairs on {timeframes}...")
        
        for pair_data in pairs:
            symbol = pair_data['Symbol'] if isinstance(pair_data, dict) else pair_data
            
            # Fetch data for ALL required timeframes for this pair
            data_map = {}
            for tf in timeframes:
                # Standardize timeframe to short codes (e.g. '1h')
                # CCXT KuCoin fetch_ohlcv expects the key (like '1h'), not the internal '1hour'
                normalized_tf = self.normalize_timeframe(tf)
                
                # Fetch 500 candles with instance isolation
                df = fetcher.fetch_and_sync(instance_id, symbol, normalized_tf, limit=500)
                if df is not None and not df.empty:
                    data_map[tf] = df
                else:
                    logger.warning(f"No data fetched for {symbol} ({tf}) for instance {instance['name']}")

            # If we have data for all timeframes, proceed to analysis
            if len(data_map) == len(timeframes):
                # Calculate indicators for all timeframes
                processed_data = {}
                valid_set = True
                for tf in data_map:
                    df_tf = data_map[tf]
                    # Strategy needs enough data for indicators (EMA 200 needs 200+)
                    if df_tf is None or len(df_tf) < 20: # Loose check for RSI/EMA10
                        valid_set = False
                        break
                    processed_data[tf] = self.strategy.calculate_indicators(df_tf)

                if not valid_set:
                    continue

                # Trend Logic: Requires at least 2 timeframes
                trend = "NEUTRAL"
                if len(timeframes) >= 3:
                    try:
                        # Logic assumes timeframes are sorted smallest to largest
                        # e.g. ["1h", "4h", "1d"] -> med is "4h", large is "1d"
                        df_large = processed_data[timeframes[2]]
                        df_med = processed_data[timeframes[1]]
                        
                        if len(df_large) >= 200 and len(df_med) >= 200:
                            trend = self.strategy.check_trend(df_large, df_med)
                            logger.info(f"Trend for {symbol} using {timeframes[2]}/{timeframes[1]}: {trend}")
                    except Exception as e:
                        logger.error(f"Trend check failed for {symbol}: {e}")
                
                # Trigger Logic: Primary timeframe (usually smallest)
                primary_tf = timeframes[0]
                try:
                    signal = self.strategy.check_trigger(processed_data[primary_tf], trend)
                    if signal:
                        logger.info(f"🚀 SIGNAL [{instance['name']}]: {signal} on {symbol} ({primary_tf})")
                        # TODO: Send to Analyze Agent
                except Exception as e:
                    logger.error(f"Trigger check failed for {symbol}: {e}")

    def normalize_timeframe(self, timeframe):
        """Standardize timeframe string to short codes (e.g. 1h, 15m) for CCXT consistency"""
        tf_str = str(timeframe).lower()
        if 'min' in tf_str: return tf_str.replace('min', 'm')
        if 'hour' in tf_str: return tf_str.replace('hour', 'h')
        if 'day' in tf_str: return tf_str.replace('day', 'd')
        if 'week' in tf_str: return tf_str.replace('week', 'w')
        if 'month' in tf_str: return tf_str.replace('month', 'M')
        return tf_str

    def get_time_to_next_candle(self, timeframe):
        """
        Calculate seconds until the next candle closes for a given timeframe.
        Supports short codes (1h, 15m) and long codes (1hour, 15min).
        """
        now = datetime.now(timezone.utc)
        norm = self.normalize_timeframe(timeframe)
        
        try:
            # Extract numerical value
            val_match = re.search(r"(\d+)", norm)
            val = int(val_match.group(1)) if val_match else 1
            
            if 'm' in norm:
                next_boundary = now.replace(second=0, microsecond=0) + timedelta(minutes=val - (now.minute % val))
            elif 'h' in norm:
                next_boundary = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=val - (now.hour % val))
            elif 'd' in norm:
                next_boundary = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=val)
            elif 'w' in norm:
                # Start of week
                days_to_monday = now.weekday()
                next_boundary = (now - timedelta(days=days_to_monday)).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(weeks=val)
            else:
                return 60 # Default

            wait = (next_boundary - now).total_seconds()
            return max(0, wait) + 5 # Add 5s buffer
        except Exception as e:
            logger.error(f"Error calculating next candle for {timeframe}: {e}")
            return 60

    def cleanup_instance_data(self, instance_id):
        """Clean up candles associated ONLY with this specific instance_id"""
        CANDLES_DB = "candles.db"
        try:
            conn = sqlite3.connect(CANDLES_DB)
            conn.execute("DELETE FROM candles WHERE instance_id=?", (instance_id,))
            conn.commit()
            conn.close()
            logger.info(f"🧼 Cleaned candles for instance {instance_id}")
        except Exception as e:
            logger.error(f"Failed candle cleanup for {instance_id}: {e}")

if __name__ == "__main__":
    engine = HiveEngine()
    engine.load_instances() # Initial load
    while True:
        try:
            engine.run_cycle()
        except KeyboardInterrupt:
            logger.info("Hive Engine Stopped.")
            break
        except Exception as e:
            logger.critical(f"Hive Crash: {e}")
            time.sleep(10)
