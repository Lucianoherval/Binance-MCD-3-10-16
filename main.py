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

MAX_COMPRAS = 7                     # Máximo de entradas na mesma moeda (ex: 1 compra principal + 3 recompras)
DISTANCIA_MINIMA_QUEDA = 0.02       # O preço deve cair pelo menos 2% (0.02) em relação à última compra para recomprar
LUCRO_MINIMO_PERCENTUAL = 0.05      # Lucro mínimo desejado (0.05%) sobre o PREÇO MÉDIO para vender tudo
FRACAO_CAPITAL = 0.13               # Usa 25% do capital disponível na conta para cada "lote" de compra

# ==========================================
# 🧠 VARIÁVEIS DE ESTADO (Memória do Bot)
# ==========================================
posicao_aberta = False
num_compras = 0
total_investido = 0.0
total_qtd_comprada = 0.0
ultimo_preco_compra = 0.0
preco_medio = 0.0

try:
    teste = buscar_ohlcv(binance, PAR, INTERVALO, limite=10)
    print("✅ Conexão teste OK! Dados recebidos.")
except Exception as e:
    print("❌ Falha no teste inicial de conexão:", e)
    exit()

print("🤖 Bot Trader DCA Iniciado e Monitorando o Mercado...")

while True:
    try:
        # 1. BUSCAR DADOS E PREPARAR O DATAFRAME
        ohlcv = buscar_ohlcv(binance, PAR, INTERVALO)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # 2. CALCULAR INDICADORES
        df = calcular_macd(df)
        df.dropna(inplace=True)

        atual = df.iloc[-1]
        anterior = df.iloc[-2]

        dif_atual = atual['MACD_3_10_16']
        dea_atual = atual['MACDs_3_10_16']
        dif_anterior = anterior['MACD_3_10_16']
        dea_anterior = anterior['MACDs_3_10_16']
        preco_mercado = atual['close']

        # 3. VERIFICAR CRUZAMENTOS
        cruzamento_compra = (dif_anterior < dea_anterior) and (dif_atual >= dea_atual)
        cruzamento_venda = (dif_anterior > dea_anterior) and (dif_atual <= dea_atual)

        # ==========================================
        # 🟢 LÓGICA DE COMPRA (Primeira Entrada ou Recompra)
        # ==========================================
        if cruzamento_compra and num_compras < MAX_COMPRAS:
            distancia_ok = True
            
            # Se já comprou antes, exige que o preço tenha caído para valer a pena baixar o preço médio
            if num_compras > 0:
                preco_alvo_recompra = ultimo_preco_compra * (1 - DISTANCIA_MINIMA_QUEDA)
                if preco_mercado > preco_alvo_recompra:
                    distancia_ok = False
                    print(f"[{datetime.now()}] ⏳ MACD cruzou compra, mas a queda foi fraca. Preço (R${preco_mercado:.2f}) não atingiu o alvo de recompra (R${preco_alvo_recompra:.2f}).")

            if distancia_ok:
                brl_balance = binance.fetch_balance().get('total', {}).get('BRL', 0)
                
                # Define o valor da ordem. Se for a 1ª compra, usa a fração do saldo. Se for recompra, usa o mesmo lote inicial.
                valor_da_ordem = (brl_balance * FRACAO_CAPITAL) if num_compras == 0 else (total_investido / num_compras)
                valor_da_ordem = min(valor_da_ordem, brl_balance) 

                if valor_da_ordem < 15:
                    print(f"[{datetime.now()}] 💸 Saldo BRL insuficiente para a compra {num_compras + 1} (R${valor_da_ordem:.2f}).")
                else:
                    qtd_btc = math.floor((valor_da_ordem / preco_mercado) * 100000) / 100000.0
                    
                    # 🛒 EXECUTA A COMPRA NA BINANCE
                    binance.create_market_buy_order(PAR, qtd_btc)
                    
                    # Atualiza a Memória do Bot
                    num_compras += 1
                    total_qtd_comprada += qtd_btc
                    total_investido += valor_da_ordem
                    preco_medio = total_investido / total_qtd_comprada
                    ultimo_preco_compra = preco_mercado
                    posicao_aberta = True

                    registrar_operacao([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"COMPRA {num_compras}", preco_mercado, qtd_btc, "", "", "", valor_da_ordem
                    ])
                    
                    print(f"[{datetime.now()}] ✅ COMPRA {num_compras}/{MAX_COMPRAS}: {qtd_btc} BTC a R${preco_mercado:.2f}")
                    print(f"📊 NOVO PREÇO MÉDIO: R${preco_medio:.2f} | Total Investido: R${total_investido:.2f}")

        # ==========================================
        # 🔴 LÓGICA DE VENDA (Saída Total com Lucro)
        # ==========================================
        elif posicao_aberta and cruzamento_venda:
            # A regra principal muda: O bot tenta vender acima do PREÇO MÉDIO, não da última compra!
            if preco_mercado > preco_medio:
                valor_total_venda = total_qtd_comprada * preco_mercado
                lucro = valor_total_venda - total_investido
                lucro_percentual = (lucro / total_investido) * 100

                if lucro_percentual >= LUCRO_MINIMO_PERCENTUAL:
                    # 🛒 EXECUTA A VENDA DE TUDO
                    binance.create_market_sell_order(PAR, total_qtd_comprada)
                    
                    registrar_operacao([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "VENDA TOTAL", "", total_qtd_comprada, preco_mercado, valor_total_venda, lucro, total_investido
                    ])
                    
                    print(f"[{datetime.now()}] 💰 VENDA TOTAL: {total_qtd_comprada} BTC a R${preco_mercado:.2f}")
                    print(f"🎉 LUCRO GARANTIDO: R${lucro:.2f} ({lucro_percentual:.2f}%)")
                    
                    # 🧹 Reseta o bot para o próximo ciclo de operações
                    posicao_aberta = False
                    num_compras = 0
                    total_investido = 0.0
                    total_qtd_comprada = 0.0
                    ultimo_preco_compra = 0.0
                    preco_medio = 0.0
                else:
                    print(f"[{datetime.now()}] ⏳ Venda ignorada: Lucro de {lucro_percentual:.2f}% não atingiu o mínimo ({LUCRO_MINIMO_PERCENTUAL}%).")
            else:
                print(f"[{datetime.now()}] 🛑 Sinal de venda do MACD, mas o preço (R${preco_mercado:.2f}) está abaixo do seu PREÇO MÉDIO (R${preco_medio:.2f}). Segurando a moeda...")

    except Exception as e:
        print(f"[{datetime.now()}] ⚠️ Erro no ciclo: {e}")

    # Pausa antes da próxima checagem
    time.sleep(180)