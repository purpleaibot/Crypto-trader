import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Exchange Settings
    EXCHANGES = ['binance', 'kucoin', 'gateio']
    
    # Data Fetching
    CANDLE_FETCH_DELAY = 5  # Seconds after close
    TIMEFRAMES = ['15m', '30m', '1h', '4h', '1d', '1w']
    
    # Database
    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-token")
    INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "my-org")
    INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "crypto_trader")

    # Risk Management Defaults
    DEFAULT_RISK_PERCENT = 0.02  # 2%
    DEFAULT_RR_RATIO = 3.0       # 1:3
    
    # Emergency
    KILL_SWITCH_THRESHOLD = 0.50 # 50% drawdown
