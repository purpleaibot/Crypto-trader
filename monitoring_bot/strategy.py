import pandas_ta as ta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        pass

    def calculate_indicators(self, df):
        """
        Adds technical indicators to the DataFrame.
        """
        # Trend Indicators (Higher Timeframe)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        # ADX (Directional Movement)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        df = pd.concat([df, adx], axis=1) # Adds ADX_14, DMP_14 (+DI), DMN_14 (-DI)

        # Trigger Indicators (Lower Timeframe)
        df['EMA_10'] = ta.ema(df['close'], length=10)
        df['EMA_20'] = ta.ema(df['close'], length=20)
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # Volatility Filter
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        return df

    def check_trend(self, df_1d, df_4h):
        """
        Checks if the higher timeframes are aligned.
        Returns: 'UP', 'DOWN', or 'NEUTRAL'
        """
        # Get last closed candle
        last_1d = df_1d.iloc[-1]
        last_4h = df_4h.iloc[-1]
        
        # Define Trend Criteria
        # 1. Price vs EMAs
        # 2. EMA Cross
        # 3. ADX Strength (>20)
        # 4. +DI vs -DI
        
        # Check 1D Trend
        trend_1d = self._evaluate_trend(last_1d)
        
        # Check 4H Trend
        trend_4h = self._evaluate_trend(last_4h)
        
        if trend_1d == 'UP' and trend_4h == 'UP':
            return 'UP'
        elif trend_1d == 'DOWN' and trend_4h == 'DOWN':
            return 'DOWN'
        else:
            return 'NEUTRAL'

    def _evaluate_trend(self, row):
        """
        Helper to evaluate a single row's trend.
        """
        adx_threshold = 20
        
        # Uptrend Condition
        if (row['close'] > row['EMA_50'] > row['EMA_200'] and
            row['ADX_14'] > adx_threshold and
            row['DMP_14'] > row['DMN_14']):
            return 'UP'
            
        # Downtrend Condition
        if (row['close'] < row['EMA_50'] < row['EMA_200'] and
            row['ADX_14'] > adx_threshold and
            row['DMN_14'] > row['DMP_14']):
            return 'DOWN'
            
        return 'NEUTRAL'

    def check_trigger(self, df_1h, trend_direction):
        """
        Checks for entry triggers on lower timeframe (1H) aligned with Trend.
        Returns: 'BUY', 'SELL', or None
        """
        last_row = df_1h.iloc[-1]
        prev_row = df_1h.iloc[-2] # To check for crossover
        
        # Volatility Filter (ATR)
        # TODO: Define a dynamic threshold based on asset price or %?
        # For now, ensuring it's not zero/null.
        if last_row['ATR'] == 0:
            return None

        if trend_direction == 'UP':
            # Buy Trigger: EMA 10 crosses ABOVE EMA 20 AND RSI is rising/bullish
            if (prev_row['EMA_10'] <= prev_row['EMA_20'] and 
                last_row['EMA_10'] > last_row['EMA_20'] and
                last_row['RSI'] > 40): # RSI check
                return 'BUY'
                
        elif trend_direction == 'DOWN':
            # Sell Trigger: EMA 10 crosses BELOW EMA 20 AND RSI is falling/bearish
            if (prev_row['EMA_10'] >= prev_row['EMA_20'] and 
                last_row['EMA_10'] < last_row['EMA_20'] and
                last_row['RSI'] < 60): # RSI check
                return 'SELL'
                
        return None
