# registro.py
import csv
import os
import pandas as pd

def inicializar_csv():
    if not os.path.exists("registro_operacoes.csv"):
        with open("registro_operacoes.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp","TipoOperacao","PrecodeCompra","QuntComprada","PrecodeVenda","ValorTotalVendido","Lucro","ValorInestido"])

def registrar_operacao(linha):
    with open("registro_operacoes.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(linha)

def carregar_ultima_operacao():
    try:
        df = pd.read_csv("registro_operacoes.csv")
        if not df.empty:
            ultima = df.iloc[-1]
            return ultima.to_dict()
    except:
        pass
    return {}