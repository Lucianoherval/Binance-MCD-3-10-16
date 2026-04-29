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

# ==========================================
# ⚙️ CONFIGURAÇÕES DA ESTRATÉGIA DE LOTES (Binance)
# ==========================================
MAX_LOTES = 3                    # 🔪 Quantidade de fatias
CAPITAL_INICIAL = 1239.64        # 💰 Valor Total aproximado

DISTANCIA_MINIMA_QUEDA = 0.019   # O preço deve cair pelo menos 1.9% em relação à mão anterior
LUCRO_ALVO = 0.0069              # Lucro mínimo desejado (0.69%) por cada lote individual

# ==========================================
# 🧠 MEMÓRIA DO BOT (CÉREBRO JSON)
# ==========================================
ARQUIVO_MEMORIA = "memoria_bot.json"

def lotes_padrao():
    return [{"id": i + 1, "status": "livre", "preco_compra": 0.0, "quantidade": 0.0, "valor_investido": 0.0} for i in range(MAX_LOTES)]

def salvar_memoria(memoria):
    with open(ARQUIVO_MEMORIA, "w") as f:
        json.dump(memoria, f, indent=2)

def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        with open(ARQUIVO_MEMORIA, "r") as f:
            dados = json.load(f)
        if "lotes" not in dados or len(dados["lotes"]) != MAX_LOTES:
            dados["lotes"] = lotes_padrao()
        if "capital_operacional" not in dados:
            dados["capital_operacional"] = CAPITAL_INICIAL
        if "capital_alocado" not in dados:
            dados["capital_alocado"] = sum(l["valor_investido"] for l in dados["lotes"] if l["status"] == "aberto")
        return dados
    
    return {"capital_operacional": CAPITAL_INICIAL, "capital_alocado": 0.0, "lotes": lotes_padrao()}

def preparar_dataframe(ohlcv):
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df = calcular_macd(df)
    df.dropna(inplace=True)
    return df

# ==========================================
# 🔌 CONEXÃO E INICIALIZAÇÃO
# ==========================================
binance = conectar_binance()
inicializar_csv()

memoria = carregar_memoria()
preco_mercado = 0.0
contador_telegram = 0
erros_consecutivos = 0

lotes_abertos_init = [l for l in memoria["lotes"] if l["status"] == "aberto"]
if lotes_abertos_init:
    resumo = "\n".join(f"  Lote {l['id']}: {l['quantidade']} BTC @ R${l['preco_compra']:.2f}" for l in lotes_abertos_init)
    msg_restart = (
        f"♻️ <b>BOT BINANCE REINICIADO (LOTES)</b>\n\n"
        f"<b>Lotes abertos:</b> {len(lotes_abertos_init)}/{MAX_LOTES}\n"
        f"<b>Capital alocado:</b> R$ {memoria['capital_alocado']:.2f}\n"
        f"<b>Capital livre:</b> R$ {memoria['capital_operacional']:.2f}\n\n"
        f"<b>Posições:</b>\n{resumo}"
    )
    print(f"💾 Memória Binance recuperada! {len(lotes_abertos_init)} lote(s) aberto(s).")
    enviar_telegram(msg_restart)
else:
    enviar_telegram(f"▶️ <b>Bot Binance de Lotes iniciado.</b>\nCapital Livre: R$ {memoria['capital_operacional']:.2f} | Par: {PAR}")

try:
    buscar_ohlcv(binance, PAR, INTERVALO, limite=10)
    print("✅ Conexão Binance OK! Dados recebidos.")
except Exception as e:
    print("❌ Falha no teste inicial de conexão:", e)
    enviar_telegram(f"❌ <b>Falha ao conectar na Binance!</b>\n<code>{e}</code>")
    exit()

print("🤖 Bot Binance de Lotes Independentes Iniciado...")

# ==========================================
# 🔁 LOOP PRINCIPAL
# ==========================================
while True:
    try:
        # 1. BUSCAR DADOS (Single Timeframe)
        df = preparar_dataframe(buscar_ohlcv(binance, PAR, INTERVALO))
        
        atual = df.iloc[-1]
        anterior = df.iloc[-2]
        preco_mercado = atual['close']

        cruz_compra = (anterior['MACD_3_10_16'] < anterior['MACDs_3_10_16']) and (atual['MACD_3_10_16'] >= atual['MACDs_3_10_16'])
        cruz_venda  = (anterior['MACD_3_10_16'] > anterior['MACDs_3_10_16']) and (atual['MACD_3_10_16'] <= atual['MACDs_3_10_16'])

        erros_consecutivos = 0 

        # ==========================================
        # 🔴 LÓGICA DE VENDA (Lote a Lote)
        # ==========================================
        if cruz_venda:
            for lote in memoria["lotes"]:
                if lote["status"] != "aberto":
                    continue

                lucro_pct = (preco_mercado - lote["preco_compra"]) / lote["preco_compra"]

                if lucro_pct < LUCRO_ALVO:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Lote {lote['id']}: lucro {lucro_pct*100:.2f}% abaixo do alvo ({LUCRO_ALVO*100:.2f}%).")
                    continue

                # Prepara dados para venda
                id_lote         = lote["id"]
                qtd_vender      = lote["quantidade"]
                preco_entrada   = lote["preco_compra"]
                valor_investido = lote["valor_investido"]
                lucro_brl       = (preco_mercado - preco_entrada) * qtd_vender
                valor_venda     = preco_mercado * qtd_vender

                # Verifica saldo físico na Binance para evitar erro de insuficiência
                btc_balance = binance.fetch_balance().get('total', {}).get('BTC', 0.0)
                qtd_final_venda = min(qtd_vender, btc_balance)

                # 🛒 EXECUTA A VENDA NA BINANCE
                binance.create_market_sell_order(PAR, qtd_final_venda)

                # Atualiza memória
                lote["status"]          = "livre"
                lote["preco_compra"]    = 0.0
                lote["quantidade"]      = 0.0
                lote["valor_investido"] = 0.0

                memoria["capital_operacional"] += valor_venda
                memoria["capital_alocado"]     -= valor_investido
                salvar_memoria(memoria)

                registrar_operacao([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"VENDA LOTE {id_lote}", preco_entrada, qtd_final_venda, preco_mercado, valor_venda, lucro_brl, valor_investido
                ])

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💰 LOTE {id_lote} VENDIDO: {qtd_final_venda} BTC @ R${preco_mercado:.2f} | Lucro: R${lucro_brl:.2f}")
                enviar_telegram(
                    f"💰 <b>LOTE {id_lote} VENDIDO!</b>\n\n"
                    f"<b>Par:</b> {PAR}\n"
                    f"<b>Qtd:</b> {qtd_final_venda} BTC\n"
                    f"<b>Entrada:</b> R$ {preco_entrada:.2f}\n"
                    f"<b>Saída:</b> R$ {preco_mercado:.2f}\n"
                    f"<b>Lucro:</b> R$ {lucro_brl:.2f} ({lucro_pct*100:.2f}%)\n\n"
                    f"🏦 <b>Capital livre:</b> R$ {memoria['capital_operacional']:.2f}"
                )

        # ==========================================
        # 🟢 LÓGICA DE COMPRA (Um lote por cruzamento)
        # ==========================================
        if cruz_compra:
            compra_executada = False
            lotes_abertos_agora = [l for l in memoria["lotes"] if l["status"] == "aberto"]

            for lote in memoria["lotes"]:
                if compra_executada:
                    break
                if lote["status"] != "livre":
                    continue

                permissao = True
                msg_bloqueio = ""

                # Regra de Distância Mínima
                if len(lotes_abertos_agora) > 0:
                    ultimo_aberto = max(lotes_abertos_agora, key=lambda l: l["preco_compra"])
                    preco_alvo    = ultimo_aberto["preco_compra"] * (1 - DISTANCIA_MINIMA_QUEDA)

                    if preco_mercado > preco_alvo:
                        permissao = False
                        msg_bloqueio = (
                            f"⏳ <b>RECOMPRA BLOQUEADA — Queda insuficiente</b>\n\n"
                            f"<b>Distância exigida:</b> {DISTANCIA_MINIMA_QUEDA*100:.1f}%\n"
                            f"<b>Preço atual:</b> R$ {preco_mercado:.2f}\n"
                            f"<b>Alvo necessário:</b> R$ {preco_alvo:.2f}\n"
                            f"<b>Falta cair:</b> R$ {preco_mercado - preco_alvo:.2f}"
                        )

                if not permissao:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bloqueio: {msg_bloqueio[:60].replace(chr(10),' ')}")
                    break 

                brl_balance = binance.fetch_balance().get('total', {}).get('BRL', 0)
                
                # O bolo total soma o que está preso e o que está livre
                bolo_total = memoria["capital_operacional"] + memoria["capital_alocado"]
                valor_da_ordem = bolo_total / MAX_LOTES

                if valor_da_ordem > brl_balance:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 💸 Saldo BRL livre (R${brl_balance:.2f}) é insuficiente.")
                    break
                elif valor_da_ordem < 10:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 💸 A fatia calculada (R${valor_da_ordem:.2f}) é menor que o limite (R$10.00).")
                    break

                qtd_btc = math.floor((valor_da_ordem / preco_mercado) * 100000) / 100000.0
                valor_real_gasto = qtd_btc * preco_mercado

                # 🛒 EXECUTA A COMPRA NA BINANCE
                binance.create_market_buy_order(PAR, qtd_btc)

                # Atualiza memória
                lote["status"]          = "aberto"
                lote["preco_compra"]    = preco_mercado
                lote["quantidade"]      = qtd_btc
                lote["valor_investido"] = valor_real_gasto

                memoria["capital_operacional"] -= valor_real_gasto
                memoria["capital_alocado"]     += valor_real_gasto
                salvar_memoria(memoria)

                registrar_operacao([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"COMPRA LOTE {lote['id']}", preco_mercado, qtd_btc, "", "", "", valor_real_gasto
                ])

                lotes_abertos_pos = len([l for l in memoria["lotes"] if l["status"] == "aberto"])
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ LOTE {lote['id']} COMPRADO: {qtd_btc} BTC @ R${preco_mercado:.2f} | Livre: R${memoria['capital_operacional']:.2f}")
                enviar_telegram(
                    f"🛒 <b>LOTE {lote['id']} COMPRADO ({lotes_abertos_pos}/{MAX_LOTES})</b>\n\n"
                    f"<b>Par:</b> {PAR}\n"
                    f"<b>Quantidade:</b> {qtd_btc} BTC\n"
                    f"<b>Preço:</b> R$ {preco_mercado:.2f}\n"
                    f"<b>Investido:</b> R$ {valor_real_gasto:.2f}\n\n"
                    f"🏦 <b>Capital livre:</b> R$ {memoria['capital_operacional']:.2f}"
                )
                compra_executada = True

    except Exception as e:
        erros_consecutivos += 1
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro Binance ({erros_consecutivos}x): {e}")

    # ==========================================
    # 🖥️ PAINEL DE STATUS
    # ==========================================
    contador_telegram += 1
    if contador_telegram >= 63:
        lotes_status = [l for l in memoria["lotes"] if l["status"] == "aberto"]
        if lotes_status:
            linhas = []
            for l in lotes_status:
                var = ((preco_mercado - l["preco_compra"]) / l["preco_compra"] * 100) if l["preco_compra"] > 0 else 0
                linhas.append(f"  Lote {l['id']}: R${l['preco_compra']:.2f} → {'+' if var>=0 else ''}{var:.2f}%")
            enviar_telegram(
                f"📊 <b>STATUS BINANCE</b>\n\n"
                f"<b>Par:</b> {PAR}\n"
                f"<b>Preço atual:</b> R$ {preco_mercado:.2f}\n"
                f"<b>Lotes abertos:</b> {len(lotes_status)}/{MAX_LOTES}\n"
                + "\n".join(linhas) +
                f"\n\n🏦 <b>Capital livre:</b> R$ {memoria['capital_operacional']:.2f}"
            )
        else:
            enviar_telegram(
                f"🔎 <b>BUSCANDO SINAL</b>\n\n"
                f"<b>Par:</b> {PAR}\n"
                f"<b>Preço atual:</b> R$ {preco_mercado:.2f}\n"
                f"<b>Distância exigida:</b> {DISTANCIA_MINIMA_QUEDA*100:.1f}%\n"
                f"🏦 <b>Capital livre:</b> R$ {memoria['capital_operacional']:.2f}"
            )
        contador_telegram = 0

    lotes_ab = len([l for l in memoria["lotes"] if l["status"] == "aberto"])
    if lotes_ab > 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 R${preco_mercado:.2f} | Lotes: {lotes_ab}/{MAX_LOTES} | Livre: R${memoria['capital_operacional']:.2f}")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 R${preco_mercado:.2f} | Buscando... | Capital: R${memoria['capital_operacional']:.2f}")

    time.sleep(69)