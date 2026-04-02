import ccxt
from config import BINANCE_API_KEY, BINANCE_API_SECRET

def conectar_binance():
    return ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True  # <- ADICIONE ESSA LINHA
        }
    })

def buscar_ohlcv(binance, par, intervalo='1h', limite=100):
    ohlcv = binance.fetch_ohlcv(par, timeframe=intervalo, limit=limite)
    return ohlcv
