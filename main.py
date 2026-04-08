import time
import pandas as pd
import math
import requests
import json
import os
from datetime import datetime
from binance_trader import conectar_binance, buscar_ohlcv
from indicadores import calcular_macd
from registro import inicializar_csv, registrar_operacao
from config import PAR, INTERVALO, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

# ==========================================
# 📱 ALERTA TELEGRAM
# ==========================================
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML" 
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Erro ao enviar notificação para o Telegram: {e}")

binance = conectar_binance()
inicializar_csv()

# ==========================================
# ⚙️ CONFIGURAÇÕES DA ESTRATÉGIA DCA
# ==========================================
INVESTIMENTO_INICIAL = 100.00       # 💰 SEU BOLO TOTAL: O valor exato que o bot vai fatiar
MAX_COMPRAS = 5                     # 🔪 QUANTIDADE DE FATIAS: Dividirá o bolo por esse número (Ex: 100 / 5 = 20 por entrada)

DISTANCIA_MINIMA_QUEDA = 0.02       # O preço deve cair pelo menos 2%
LUCRO_MINIMO_PERCENTUAL = 0.05      # Lucro mínimo desejado (0.05%) sobre o PREÇO MÉDIO

# ==========================================
# 🧠 MEMÓRIA DO BOT (CÉREBRO JSON)
# ==========================================
ARQUIVO_MEMORIA = "memoria_bot.json"

def salvar_memoria(estado):
    with open(ARQUIVO_MEMORIA, "w") as f:
        json.dump(estado, f)

def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        with open(ARQUIVO_MEMORIA, "r") as f:
            return json.load(f)
    return None

# Inicializando as variáveis padrão
posicao_aberta = False
num_compras = 0
total_investido = 0.0
total_qtd_comprada = 0.0
ultimo_preco_compra = 0.0
preco_medio = 0.0
capital_operacional = INVESTIMENTO_INICIAL # Essa variável cresce com os lucros
contador_telegram = 0

# Tentando carregar a memória se o bot foi reiniciado
memoria_salva = carregar_memoria()
if memoria_salva:
    posicao_aberta = memoria_salva.get("posicao_aberta", False)
    num_compras = memoria_salva.get("num_compras", 0)
    total_investido = memoria_salva.get("total_investido", 0.0)
    total_qtd_comprada = memoria_salva.get("total_qtd_comprada", 0.0)
    ultimo_preco_compra = memoria_salva.get("ultimo_preco_compra", 0.0)
    preco_medio = memoria_salva.get("preco_medio", 0.0)
    capital_operacional = memoria_salva.get("capital_operacional", INVESTIMENTO_INICIAL)
    
    if posicao_aberta:
        print(f"💾 Memória recuperada! O bot lembra que tem {num_compras} compra(s) aberta(s). Preço Médio: R${preco_medio:.2f}")

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

        atual = df.iloc[-2]
        anterior = df.iloc[-3]

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
            
            if num_compras > 0:
                preco_alvo_recompra = ultimo_preco_compra * (1 - DISTANCIA_MINIMA_QUEDA)
                if preco_mercado > preco_alvo_recompra:
                    distancia_ok = False
                    print(f"[{datetime.now()}] ⏳ MACD cruzou compra, mas a queda foi fraca. Preço (R${preco_mercado:.2f}) não atingiu o alvo (R${preco_alvo_recompra:.2f}).")

            if distancia_ok:
                brl_balance = binance.fetch_balance().get('total', {}).get('BRL', 0)
                
                # 🛠️ A NOVA MATEMÁTICA DA DIVISÃO (Ex: 100 / 5 = 20)
                valor_da_ordem = capital_operacional / MAX_COMPRAS

                if valor_da_ordem > brl_balance:
                    print(f"[{datetime.now()}] 💸 Saldo BRL livre na corretora (R${brl_balance:.2f}) é insuficiente para a fatia de R${valor_da_ordem:.2f}.")
                elif valor_da_ordem < 10:
                    print(f"[{datetime.now()}] 💸 A fatia calculada (R${valor_da_ordem:.2f}) é menor que o limite da Binance (R$10.00). Aumente o INVESTIMENTO_INICIAL.")
                else:
                    # Cálculo seguro do Bitcoin
                    qtd_btc = math.floor((valor_da_ordem / preco_mercado) * 100000) / 100000.0
                    valor_real_gasto = qtd_btc * preco_mercado
                    
                    # 🛒 EXECUTA A COMPRA NA BINANCE
                    binance.create_market_buy_order(PAR, qtd_btc)
                    
                    # Atualiza a Memória do Bot
                    num_compras += 1
                    total_qtd_comprada += qtd_btc
                    total_investido += valor_real_gasto 
                    preco_medio = total_investido / total_qtd_comprada
                    ultimo_preco_compra = preco_mercado
                    posicao_aberta = True

                    # 💾 Salva o estado atual no Cérebro (JSON)
                    salvar_memoria({
                        "posicao_aberta": posicao_aberta,
                        "num_compras": num_compras,
                        "total_investido": total_investido,
                        "total_qtd_comprada": total_qtd_comprada,
                        "ultimo_preco_compra": ultimo_preco_compra,
                        "preco_medio": preco_medio,
                        "capital_operacional": capital_operacional
                    })

                    registrar_operacao([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"COMPRA {num_compras}", preco_mercado, qtd_btc, "", "", "", valor_real_gasto
                    ])
                    
                    print(f"[{datetime.now()}] ✅ COMPRA {num_compras}/{MAX_COMPRAS}: {qtd_btc} BTC a R${preco_mercado:.2f}")
                    print(f"📊 NOVO PREÇO MÉDIO: R${preco_medio:.2f} | Total Investido: R${total_investido:.2f}")

                    # 📱 Alerta Telegram
                    msg_compra = f"🛒 <b>COMPRA EXECUTADA ({num_compras}/{MAX_COMPRAS})</b>\n\n<b>Par:</b> {PAR}\n<b>Quantidade:</b> {qtd_btc} BTC\n<b>Preço:</b> R$ {preco_mercado:.2f}\n<b>Investido:</b> R$ {valor_real_gasto:.2f}\n\n📊 <b>Novo Preço Médio:</b> R$ {preco_medio:.2f}"
                    enviar_telegram(msg_compra)

        # ==========================================
        # 🔴 LÓGICA DE VENDA (Saída Total com Lucro)
        # ==========================================
        elif posicao_aberta and cruzamento_venda:
            if preco_mercado > preco_medio:
                valor_total_venda = total_qtd_comprada * preco_mercado
                lucro = valor_total_venda - total_investido
                lucro_percentual = (lucro / total_investido) * 100

                if lucro_percentual >= LUCRO_MINIMO_PERCENTUAL:
                    # 🛒 EXECUTA A VENDA DE TUDO
                    btc_balance = binance.fetch_balance().get('total', {}).get('BTC', 0.0)
                    qtd_para_venda = min(total_qtd_comprada, brl_balance)
                    binance.create_market_sell_order(PAR, qtd_para_venda)
                    
                    registrar_operacao([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "VENDA TOTAL", "", total_qtd_comprada, preco_mercado, valor_total_venda, lucro, total_investido
                    ])
                    
                    print(f"[{datetime.now()}] 💰 VENDA TOTAL: {total_qtd_comprada} BTC a R${preco_mercado:.2f}")
                    print(f"🎉 LUCRO GARANTIDO: R${lucro:.2f} ({lucro_percentual:.2f}%)")
                    
                    # 📈 Juros Compostos: Soma o lucro ao bolo total
                    capital_operacional += lucro
                    print(f"🏦 Novo Capital Operacional para o próximo ciclo: R${capital_operacional:.2f}")

                    # 📱 Alerta Telegram
                    msg_venda = f"💰 <b>VENDA COM LUCRO!</b>\n\n<b>Par:</b> {PAR}\n<b>Preço de Saída:</b> R$ {preco_mercado:.2f}\n🎉 <b>LUCRO:</b> R$ {lucro:.2f} ({lucro_percentual:.2f}%)\n🏦 <b>Novo Capital:</b> R$ {capital_operacional:.2f}"
                    enviar_telegram(msg_venda)
                    
                    # 🧹 Reseta o bot e apaga a memória
                    posicao_aberta = False
                    num_compras = 0
                    total_investido = 0.0
                    total_qtd_comprada = 0.0
                    ultimo_preco_compra = 0.0
                    preco_medio = 0.0
                    
                    salvar_memoria({
                        "posicao_aberta": False, "num_compras": 0, "total_investido": 0.0, 
                        "total_qtd_comprada": 0.0, "ultimo_preco_compra": 0.0, "preco_medio": 0.0, 
                        "capital_operacional": capital_operacional # Salva o bolo gordo para a próxima vez
                    })
                else:
                    print(f"[{datetime.now()}] ⏳ Venda ignorada: Lucro de {lucro_percentual:.2f}% não atingiu o mínimo ({LUCRO_MINIMO_PERCENTUAL}%).")
            else:
                print(f"[{datetime.now()}] 🛑 Sinal de venda, mas o preço (R${preco_mercado:.2f}) está abaixo do seu PREÇO MÉDIO (R${preco_medio:.2f}).")

    except Exception as e:
        print(f"[{datetime.now()}] ⚠️ Erro no ciclo: {e}")
    
    # ==========================================
    # 🖥️ PAINEL DE STATUS E AVISO TELEGRAM
    # ==========================================
    if posicao_aberta:
        msg_status = f"📊 STATUS | Preço Atual: R${preco_mercado:.2f} | Seu Preço Médio: R${preco_medio:.2f} | Lotes: {num_compras}/{MAX_COMPRAS}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg_status}")
    else:
        msg_busca = f"🔎 BUSCANDO OPORTUNIDADES | Preço Atual: R${preco_mercado:.2f} | Bolo Atual: R${capital_operacional:.2f}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg_busca}")
        
        # Avisa no Telegram a cada ~1 hora
        contador_telegram += 1
        if contador_telegram >= 34: 
            enviar_telegram(msg_busca)
            contador_telegram = 0   

    # Pausa antes da próxima checagem
    time.sleep(67)