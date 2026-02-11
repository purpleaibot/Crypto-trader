import ccxt
import time
import pandas as pd
from datetime import datetime, timedelta
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, exchange_id='binance'):
        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)()
        self.exchange.load_markets()
        logger.info(f"Initialized {exchange_id} DataFetcher")

    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        """
        Fetches the last N candles for a symbol.
        Ensures we get CLOSED candles by checking timestamps.
        """
        try:
            # Calculate timestamp for 'limit' candles ago to optimize fetch
            since = self.exchange.milliseconds() - (limit * self.exchange.parse_timeframe(timeframe) * 1000)
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            
            # Validation: Option B (Check Timestamp continuity & integrity)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Check if the last candle is actually closed
            # Current time
            now = datetime.utcnow()
            # Duration of one candle in seconds
            duration_seconds = self.exchange.parse_timeframe(timeframe)
            
            # Remove the last candle if it's strictly the "current/open" one
            # Logic: If last_candle_time + duration > now, it's still open.
            last_candle_time = df.iloc[-1]['timestamp']
            if last_candle_time + timedelta(seconds=duration_seconds) > now:
                df = df.iloc[:-1]
                
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return None

    def validate_candles(self, df):
        """
        Option B: Strict Validation
        Checks for gaps in timestamps and data integrity.
        """
        # TODO: Implement strict gap detection logic
        if df.isnull().values.any():
            logger.warning("Found null values in candle data")
            return False
        return True
