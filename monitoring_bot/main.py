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
        self.next_wake_times = {} # {instance_id: next_wake_timestamp}
        logger.info("🐝 Hive Engine Initialized")

    def load_instances(self):
        """Load ACTIVE instances from DB and handle DELETED ones"""
        try:
            conn = sqlite3.connect(DB_PATH)
            # Ensure table exists with instance_id column
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
                        "timeframes": config.get('strategy', {}).get('timeframes', ['1h'])
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
                    # Ideally stop the subprocesses too here
                    
        except Exception as e:
            logger.error(f"Error loading instances: {e}")

    def get_next_event_time(self):
        """
        Calculate the earliest time any active instance needs to run a cycle.
        """
        if not self.active_instances:
            return time.time() + 10 # Default wait if no instances

        min_wait = float('inf')
        for iid, instance in self.active_instances.items():
            if iid not in self.next_wake_times:
                # First time, calculate for all its timeframes
                instance_min_wait = float('inf')
                for tf in instance['timeframes']:
                    wait = self.get_time_to_next_candle(tf)
                    instance_min_wait = min(instance_min_wait, wait)
                self.next_wake_times[iid] = time.time() + instance_min_wait
            
            min_wait = min(min_wait, self.next_wake_times[iid])
        
        return min_wait

    def run_cycle(self):
        """Main execution loop with Smart Sleep"""
        self.load_instances()
        
        if not self.active_instances:
            logger.info("💤 No active instances. Waiting 10s...")
            time.sleep(10)
            return

        current_time = time.time()
        next_event_time = self.get_next_event_time()
        
        if current_time < next_event_time:
            sleep_duration = next_event_time - current_time
            logger.info(f"✅ Cycle complete. Waiting {sleep_duration:.1f}s for next event.")
            time.sleep(sleep_duration)

        logger.info(f"🔄 Processing {len(self.active_instances)} instances...")
        
        # Process instances that are due
        for iid, instance in list(self.active_instances.items()): # Use list to allow modification during iteration
            needs_processing = False
            current_instance_min_sleep = float('inf')

            for tf in instance['timeframes']:
                # Check if this timeframe needs processing NOW
                if self.next_wake_times.get(iid, float('inf')) <= time.time():
                    needs_processing = True
                    # Recalculate wait time for this timeframe
                    wait = self.get_time_to_next_candle(tf)
                    current_instance_min_sleep = min(current_instance_min_sleep, wait)
                else:
                    # If not due, but need to know when it IS due for overall min_sleep calculation
                    current_instance_min_sleep = min(current_instance_min_sleep, self.next_wake_times.get(iid, float('inf')))
            
            if needs_processing:
                try:
                    self.process_instance(instance)
                    self.next_wake_times[iid] = time.time() + current_instance_min_sleep # Reschedule
                except Exception as e:
                    logger.error(f"Error processing {instance['name']}: {e}")
                    # Potentially mark instance as ERROR or retry after a delay

            # If no timeframes need processing NOW for this instance, still update next_wake_times for future calculations if needed
            if not needs_processing and iid in self.next_wake_times:
                 pass # Keep existing next_wake_time

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
                # Map timeframe string to exchange-specific format
                exchange_tf = fetcher.exchange.timeframes.get(tf, tf)
                
                # Fetch 500 candles with instance isolation
                df = fetcher.fetch_and_sync(instance_id, symbol, exchange_tf, limit=500)
                if df is not None and not df.empty:
                    data_map[tf] = df
                else:
                    logger.warning(f"No data fetched for {symbol} ({tf}) for instance {instance['name']}")

            # Analysis logic remains...
            if data_map:
                primary_tf = timeframes[0]
                if primary_tf in data_map:
                    df = data_map[primary_tf]
                    df = self.strategy.calculate_indicators(df)
                    
                    trend = "NEUTRAL"
                    if len(timeframes) > 1:
                        trend_tf = timeframes[1]
                        if trend_tf in data_map:
                           trend = self.strategy.check_trend(data_map[trend_tf], None)
                           logger.info(f"Trend on {trend_tf}: {trend}")

                    signal = self.strategy.check_trigger(df, trend)
                    
                    if signal:
                        logger.info(f"🚀 SIGNAL [{instance['name']}]: {signal} on {symbol} ({primary_tf})")
                        # TODO: Send to Analyze Agent with instance_id
                        # self.send_to_agent(instance['id'], symbol, signal, ...)

    def get_time_to_next_candle(self, timeframe):
        """
        Calculate seconds until the next candle closes for a given timeframe.
        """
        now = datetime.utcnow()
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            delta = timedelta(minutes=minutes)
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            delta = timedelta(hours=hours)
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            delta = timedelta(days=days)
        else:
            return 60 # Default

        # Logic: find next boundary
        # For minutes/hours, we align to the start of the epoch or a fixed point
        # Simpler version:
        total_seconds = delta.total_seconds()
        elapsed = (now - datetime(1970, 1, 1)).total_seconds()
        wait = total_seconds - (elapsed % total_seconds)
        return wait

    def cleanup_instance_data(self, instance_id):
        """Clean up candles associated ONLY with this specific instance_id"""
        CANDLES_DB = "candles.db"
        try:
            conn = sqlite3.connect(CANDLES_DB)
            # Delete candles for this specific instance_id
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
