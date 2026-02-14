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
        Supports the full library available in Strategy Builder.
        """
        # Basic Price Smoothing
        df['EMA_10'] = ta.ema(df['close'], length=10)
        df['EMA_20'] = ta.ema(df['close'], length=20)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        df['SMA_20'] = ta.sma(df['close'], length=20)
        
        # Momentum
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # MACD
        macd = ta.macd(df['close'])
        if macd is not None:
            df = pd.concat([df, macd], axis=1) # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

        # Trend Strength
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None:
            df = pd.concat([df, adx], axis=1) # ADX_14, DMP_14 (+DI), DMN_14 (-DI)

        # Volatility
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Bollinger Bands
        bb = ta.bbands(df['close'], length=20, std=2)
        if bb is not None:
            df = pd.concat([df, bb], axis=1) # BBL_20_2.0, BBM_20_2.0, BBU_20_2.0

        # Ichimoku
        try:
            ichi = ta.ichimoku(df['high'], df['low'], df['close'])[0]
            df = pd.concat([df, ichi], axis=1) # ISA_9, ISB_26, ITS_9, IKS_26, ICS_26
        except: pass

        # VWAP (Requires Volume)
        if 'volume' in df.columns:
            df['VWAP'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        
        return df

    def evaluate_dynamic_rules(self, df, rules):
        """
        Evaluates a list of logical rules against the dataframe.
        Returns True if ALL rules pass (AND logic).
        """
        if not rules: return True # No rules = Pass (or handle as False?)
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        for rule in rules:
            try:
                # 1. Get Value A
                # Handle basic indicators mappings
                ind_a = self._map_indicator_name(rule['a'], rule.get('pa'))
                val_a = last_row.get(ind_a)
                prev_val_a = prev_row.get(ind_a)
                
                # 2. Get Value B
                if rule['target'] == 'value':
                    val_b = float(rule['val'])
                    prev_val_b = val_b
                else:
                    ind_b = self._map_indicator_name(rule['b'], rule.get('pb'))
                    val_b = last_row.get(ind_b)
                    prev_val_b = prev_row.get(ind_b)

                if val_a is None or val_b is None:
                    return False

                # 3. Compare based on Operator
                op = rule['op']
                if op == '>':
                    if not (val_a > val_b): return False
                elif op == '<':
                    if not (val_a < val_b): return False
                elif op == 'equals':
                    if not (val_a == val_b): return False
                elif op == 'crosses above':
                    # (Prev A <= Prev B) AND (Curr A > Curr B)
                    if not (prev_val_a <= prev_val_b and val_a > val_b): return False
                elif op == 'crosses below':
                    # (Prev A >= Prev B) AND (Curr A < Curr B)
                    if not (prev_val_a >= prev_val_b and val_a < val_b): return False
                    
            except Exception as e:
                logger.error(f"Rule evaluation error: {rule} -> {e}")
                return False
                
        return True

    def _map_indicator_name(self, name, param):
        """Helper to map UI names to Pandas TA column names"""
        # Defaults if param empty
        p = param if param else "14"
        
        if name == "RSI": return f"RSI_{p}" if f"RSI_{p}" in ["RSI_14"] else "RSI" # Fallback simplified
        if name == "EMA": return f"EMA_{p}"
        if name == "SMA": return f"SMA_{p}"
        if name == "ADX": return f"ADX_{p}"
        if name == "ATR": return f"ATR_{p}"
        if name == "VWAP": return "VWAP_D" # Standard daily VWAP
        # Add more mappings as needed
        return name

    def check_dynamic_signal(self, data_map, strategy_logic, timeframes):
        """
        Evaluates the full strategy logic from the UI configuration.
        """
        # 1. Trend Filter (Medium & Large)
        # If rules exist for Med/Large, they MUST be true to proceed.
        # Trend is "aligned" if all trend rules pass.
        
        trend_aligned = True
        
        # Check Large TF Rules (if any)
        if len(timeframes) >= 3 and strategy_logic.get('large'):
            tf_large = timeframes[2]
            if tf_large in data_map:
                if not self.evaluate_dynamic_rules(data_map[tf_large], strategy_logic['large']):
                    trend_aligned = False

        # Check Medium TF Rules (if any)
        if len(timeframes) >= 2 and strategy_logic.get('med'):
            tf_med = timeframes[1]
            if tf_med in data_map:
                if not self.evaluate_dynamic_rules(data_map[tf_med], strategy_logic['med']):
                    trend_aligned = False
        
        if not trend_aligned:
            return None

        # 2. Entry Trigger (Small TF)
        # Assuming we look for a "BUY" trigger conditions. 
        # TODO: UI needs to specify if the strategy is Long or Short.
        # For MVP, assuming these rules define a LONG entry.
        
        tf_small = timeframes[0]
        if tf_small in data_map and strategy_logic.get('small'):
            if self.evaluate_dynamic_rules(data_map[tf_small], strategy_logic['small']):
                return "BUY" # Dynamic logic triggered
        
        return None

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
        
        # Check if indicators exist (UI safety check)
        if 'EMA_50' not in row or 'EMA_200' not in row or 'ADX_14' not in row:
            return 'NEUTRAL'
            
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

    def get_row_trend(self, row):
        """Public wrapper for UI trend display"""
        return self._evaluate_trend(row)

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
