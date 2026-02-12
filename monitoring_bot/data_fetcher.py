import ccxt
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, exchange_id='binance', market_type='Spot', db_path='candles.db'):
        self.exchange_id = exchange_id
        self.market_type = market_type
        
        # Initialize Exchange with Options (Futures vs Spot)
        exchange_class = getattr(ccxt, exchange_id)
        options = {}
        if market_type == 'Futures':
            options = {'defaultType': 'future'}
        elif market_type == 'Spot':
            options = {'defaultType': 'spot'}
            
        self.exchange = exchange_class(options)
        self.exchange.load_markets()
        
        self.db_path = db_path
        self._init_db()
        logger.info(f"Initialized {exchange_id} ({market_type}) DataFetcher with DB {db_path}")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                instance_id TEXT,
                exchange TEXT,
                symbol TEXT,
                timeframe TEXT,
                timestamp DATETIME,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (instance_id, symbol, timeframe, timestamp)
            )
        ''')
        conn.commit()
        conn.close()

    def fetch_and_sync(self, instance_id, symbol, timeframe, limit=500):
        """
        Main logic: Check local DB, fetch missing, validate order, and store.
        """
        # 1. Get latest timestamp from DB
        last_ts = self._get_last_timestamp(instance_id, symbol, timeframe)
        
        # 2. Fetch from exchange
        if last_ts:
            # Fetch since last known candle
            # ccxt fetch_ohlcv since is in ms
            since = int(last_ts.timestamp() * 1000) + 1
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        else:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        if not ohlcv:
            return self.get_local_candles(instance_id, symbol, timeframe, limit)

        # 3. Validate & Save
        df_new = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        
        # Ensure only CLOSED candles are saved (with 5s buffer)
        now = datetime.utcnow()
        duration_seconds = self.exchange.parse_timeframe(timeframe)
        
        # 5-second rule: Only save if candle closed at least 5s ago
        df_new = df_new[df_new['timestamp'] + timedelta(seconds=duration_seconds + 5) <= now]

        if not df_new.empty:
            self._save_to_db(instance_id, df_new, symbol, timeframe)

        return self.get_local_candles(instance_id, symbol, timeframe, limit)

    def _get_last_timestamp(self, instance_id, symbol, timeframe):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(timestamp) FROM candles 
            WHERE instance_id = ? AND symbol = ? AND timeframe = ?
        ''', (instance_id, symbol, timeframe))
        res = cursor.fetchone()[0]
        conn.close()
        return pd.to_datetime(res) if res else None

    def _save_to_db(self, instance_id, df, symbol, timeframe):
        conn = sqlite3.connect(self.db_path)
        df['instance_id'] = instance_id
        df['exchange'] = self.exchange_id
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        # Use replace or ignore for potential duplicates if sync overlaps
        df.to_sql('candles', conn, if_exists='append', index=False, method='multi')
        conn.commit()
        conn.close()

    def get_local_candles(self, instance_id, symbol, timeframe, limit=500):
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT timestamp, open, high, low, close, volume FROM candles 
            WHERE instance_id = ? AND symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC LIMIT ?
        '''
        df = pd.read_sql(query, conn, params=(instance_id, symbol, timeframe, limit))
        conn.close()
        return df.sort_values('timestamp') if not df.empty else None

    def fetch_ohlcv(self, instance_id, symbol, timeframe, limit=500):
        # Compatibility wrapper for existing code
        return self.fetch_and_sync(instance_id, symbol, timeframe, limit)
