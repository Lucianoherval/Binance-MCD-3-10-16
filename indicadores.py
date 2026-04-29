# indicadores.py
import pandas as pd

def calcular_macd(df):
    fast, slow, signal = 3, 10, 16

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

    df['MACD_3_10_16'] = ema_fast - ema_slow
    df['MACDs_3_10_16'] = df['MACD_3_10_16'].ewm(span=signal, adjust=False).mean()
    df['MACDh_3_10_16'] = df['MACD_3_10_16'] - df['MACDs_3_10_16']

    return df