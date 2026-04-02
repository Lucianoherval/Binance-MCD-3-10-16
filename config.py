import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
PAR = 'BTC/BRL'
INTERVALO = '1h'
CSV_PATH = 'dados/operacoes.csv'