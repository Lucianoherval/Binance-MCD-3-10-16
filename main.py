import time
import pandas as pd
import math
from datetime import datetime
from binance_trader import conectar_binance, buscar_ohlcv
from indicadores import calcular_macd
from registro import inicializar_csv, registrar_operacao
from config import PAR, INTERVALO

binance = conectar_binance()
inicializar_csv()

# ==========================================
# ⚙️ CONFIGURAÇÕES DA ESTRATÉGIA DCA
# ==========================================

MAX_COMPRAS = 4                     # Máximo de entradas na mesma moeda (ex: 1 compra principal + 3 recompras)
DISTANCIA_MINIMA_QUEDA = 0.02       # O preço deve cair pelo menos 2% (0.02) em relação à última compra para recomprar
LUCRO_MINIMO_PERCENTUAL = 0.05      # Lucro mínimo desejado (0.05%) sobre o PREÇO MÉDIO para vender tudo
FRACAO_CAPITAL = 0.25               # Usa 25% do capital disponível na conta para cada "lote" de compra
