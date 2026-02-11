import time
import logging
import requests
from config import Config
from data_fetcher import DataFetcher
from capital_manager import CapitalManager
from strategy import Strategy

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MonitoringBot")

ANALYZE_AGENT_URL = "http://analyze-agent:8000/analyze"

def main():
    logger.info("Starting Monitoring Bot...")
    
    # 1. Initialize Components
    # Example Instance: 500 USDT total, 150 Start, Trading BTC/USDT on Binance
    instance_config = {
        "exchange": "binance",
        "symbol": "BTC/USDT",
        "start_amount": 150,
        "risk_percent": 0.02
    }
    
    fetcher = DataFetcher(exchange_id=instance_config["exchange"])
    cap_manager = CapitalManager(start_amount=instance_config["start_amount"])
    strategy = Strategy()
    
    logger.info(f"Instance Deployed: {instance_config['symbol']} on {instance_config['exchange']}")
    
    # 2. Main Loop (Simplified for V1 stub)
    try:
        while True:
            # 2a. Check Level
            level, min_val = cap_manager.get_current_level()
            logger.info(f"Current Level: {level} (Min Base: {min_val})")
            
            if level == "CRITICAL_LOW":
                logger.critical("KILL SWITCH TRIGGERED. Stopping instance.")
                break
                
            # 2b. Fetch Data for Multiple Timeframes (Stub: fetch 1D, 4H, 1H)
            logger.info("Fetching Market Data...")
            
            df_1d = fetcher.fetch_ohlcv(instance_config["symbol"], "1d", limit=200)
            df_4h = fetcher.fetch_ohlcv(instance_config["symbol"], "4h", limit=200)
            df_1h = fetcher.fetch_ohlcv(instance_config["symbol"], "1h", limit=50)
            
            if df_1d is not None and df_4h is not None and df_1h is not None:
                # 2c. Calculate Indicators
                df_1d = strategy.calculate_indicators(df_1d)
                df_4h = strategy.calculate_indicators(df_4h)
                df_1h = strategy.calculate_indicators(df_1h)
                
                # 2d. Check Higher Timeframe Trend (1D & 4H)
                trend_direction = strategy.check_trend(df_1d, df_4h)
                logger.info(f"Higher Timeframe Trend: {trend_direction}")
                
                if trend_direction != 'NEUTRAL':
                    # 2e. Check Lower Timeframe Trigger (1H)
                    signal = strategy.check_trigger(df_1h, trend_direction)
                    
                    if signal:
                        logger.info(f"SIGNAL DETECTED: {signal} {instance_config['symbol']}")
                        logger.info("Sending to Analyze Agent (NanoClaw)...")
                        
                        # Call NanoClaw API
                        payload = {
                            "symbol": instance_config["symbol"],
                            "timeframe": "1h",
                            "signal_type": signal,
                            "price": df_1h.iloc[-1]['close'],
                            "indicators": {
                                "rsi": df_1h.iloc[-1]['RSI'],
                                "ema_10": df_1h.iloc[-1]['EMA_10'],
                                "ema_20": df_1h.iloc[-1]['EMA_20']
                            },
                            "trend": trend_direction
                        }
                        
                        try:
                            response = requests.post(ANALYZE_AGENT_URL, json=payload, timeout=10)
                            if response.status_code == 200:
                                decision = response.json()
                                logger.info(f"NanoClaw Decision: {decision}")
                                if decision.get("decision") == "APPROVE":
                                    logger.info(">>> TRADE APPROVED! Sending to Execution Engine (Next Step)...")
                                else:
                                    logger.info(">>> TRADE REJECTED by Agent.")
                            else:
                                logger.error(f"NanoClaw Error: {response.text}")
                        except Exception as e:
                            logger.error(f"Failed to reach Analyze Agent: {e}")
                            
                    else:
                        logger.info("No trigger on 1H.")
                else:
                    logger.info("Market is Neutral/Choppy. No trade.")
                
            # Sleep to simulate interval (in real bot, this is a scheduler)
            time.sleep(60) 
            
    except KeyboardInterrupt:
        logger.info("Stopping Bot...")

if __name__ == "__main__":
    main()
