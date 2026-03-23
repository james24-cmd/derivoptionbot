import pandas as pd
import logging

def check_trend_setup(df):
    """
    If >=3 bearish candles -> PUT
    If >=3 bullish candles -> CALL
    """
    if len(df) < 3: return None
    last_3 = df.tail(3)
    
    is_bearish = all(last_3['close'] < last_3['open'])
    if is_bearish: return "PUT"
    
    is_bullish = all(last_3['close'] > last_3['open'])
    if is_bullish: return "CALL"
    
    return None

def check_reversal_setup(df):
    """
    3-5 strong candles in one direction.
    Last candle shows exhaustion (wick or small body).
    Enter opposite direction.
    """
    if len(df) < 4: return None
    
    first_3 = df.iloc[-4:-1]
    last_1 = df.iloc[-1]
    
    is_bullish_run = all((row['close'] > row['open']) for idx, row in first_3.iterrows())
    is_bearish_run = all((row['close'] < row['open']) for idx, row in first_3.iterrows())
    
    body_size = abs(last_1['close'] - last_1['open'])
    total_size = last_1['high'] - last_1['low']
    
    if total_size == 0: return None
    
    is_exhaustion = (body_size / total_size) < 0.3
    
    if is_bullish_run and is_exhaustion:
        return "PUT"
    
    if is_bearish_run and is_exhaustion:
        return "CALL"
        
    return None

def analyze_candles(df):
    rev = check_reversal_setup(df)
    if rev:
        logging.info("Reversal setup triggered.")
        return rev
        
    trend = check_trend_setup(df)
    if trend:
        logging.info("Trend setup triggered.")
        return trend
        
    return None
