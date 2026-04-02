import pandas as pd
import pandas_ta as ta

def calcular_macd(df):
    #Adiciona as colunas automaticamente ao DATA
    #Cria o MACD em 30,1,16 - MACDh 3,10,16(Histog) - MACDs 3,10,16(Sinal)
    df.ta.macd(close='close', fast=3, slow=10, signal=16, append=True)
    return df
