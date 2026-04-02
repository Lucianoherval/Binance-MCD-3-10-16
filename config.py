import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

print(BINANCE_API_KEY)
print(BINANCE_API_SECRET)

print("API Key: ", BINANCE_API_KEY)
print("API Secret: ", BINANCE_API_SECRET)