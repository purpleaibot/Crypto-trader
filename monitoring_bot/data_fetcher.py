import ccxt
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, exchange_id='binance', db_path='candles.db'):
        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)()
        self.exchange.load_markets()
        self.db_path = db_path
        self._init_db()
        logger.info(f"Initialized {exchange_id} DataFetcher with DB {db_path}")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                exchange TEXT,
                symbol TEXT,
                timeframe TEXT,
                timestamp DATETIME,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (exchange, symbol, timeframe, timestamp)
            )
        ''')
        conn.commit()
        conn.close()

    def fetch_and_sync(self, symbol, timeframe, limit=500):
        """
        Main logic: Check local DB, fetch missing, validate order, and store.
        """
        # 1. Get latest timestamp from DB
        last_ts = self._get_last_timestamp(symbol, timeframe)
        
        # 2. Fetch from exchange
        if last_ts:
            # Fetch since last known candle
            since = int(last_ts.timestamp() * 1000) + 1
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        else:
            # Initial load: Fetch last 500
            since = self.exchange.milliseconds() - (limit * self.exchange.parse_timeframe(timeframe) * 1000)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

        if not ohlcv:
            return self.get_local_candles(symbol, timeframe, limit)

        # 3. Validate & Save
        df_new = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        
        # Ensure only CLOSED candles are saved
        now = datetime.utcnow()
        duration_seconds = self.exchange.parse_timeframe(timeframe)
        df_new = df_new[df_new['timestamp'] + timedelta(seconds=duration_seconds) <= now]

        if not df_new.empty:
            self._save_to_db(df_new, symbol, timeframe)
            logger.info(f"Synced {len(df_new)} new candles for {symbol} on {self.exchange_id}")

        return self.get_local_candles(symbol, timeframe, limit)

    def _get_last_timestamp(self, symbol, timeframe):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(timestamp) FROM candles 
            WHERE exchange = ? AND symbol = ? AND timeframe = ?
        ''', (self.exchange_id, symbol, timeframe))
        res = cursor.fetchone()[0]
        conn.close()
        return pd.to_datetime(res) if res else None

    def _save_to_db(self, df, symbol, timeframe):
        conn = sqlite3.connect(self.db_path)
        df['exchange'] = self.exchange_id
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df.to_sql('candles', conn, if_exists='append', index=False, method='multi')
        conn.commit()
        conn.close()

    def get_local_candles(self, symbol, timeframe, limit=500):
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT timestamp, open, high, low, close, volume FROM candles 
            WHERE exchange = ? AND symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC LIMIT ?
        '''
        df = pd.read_sql(query, conn, params=(self.exchange_id, symbol, timeframe, limit))
        conn.close()
        return df.sort_values('timestamp') if not df.empty else None

    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        # Compatibility wrapper for existing code
        return self.fetch_and_sync(symbol, timeframe, limit)
