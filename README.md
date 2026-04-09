# Binance-MCD-3-10-16
# 🤖 Bot Trader DCA - Binance (Estratégia MACD)

Um robô de trading automatizado desenvolvido em Python para operar na corretora Binance. Ele utiliza a estratégia de **Preço Médio (Dollar Cost Averaging - DCA)** combinada com análises precisas do indicador **MACD** para encontrar os melhores pontos de compra e venda no mercado de criptomoedas.

## 📌 Visão Geral

Este bot foi projetado para operar 24/7 de forma autônoma. Diferente de bots simples, ele possui gestão de risco avançada, divide o capital em "lotes" de compra para surfar quedas de mercado (DCA), e reinveste os lucros automaticamente criando um efeito de **juros compostos**. 

A tomada de decisão é baseada no cruzamento do MACD (configuração rápida: 3, 10, 16) em tempos gráficos curtos (ex: 5 minutos), lendo apenas velas fechadas para evitar sinais falsos ("repainting").

## ✨ Principais Funcionalidades

* **Estratégia DCA Inteligente:** O bot divide o seu capital total definido em fatias e faz recompras estratégicas apenas se o preço cair uma porcentagem mínima exigida E o MACD der um novo sinal de alta.
* **Juros Compostos Automáticos:** Todo lucro obtido em uma venda bem-sucedida é automaticamente somado ao bolo do capital operacional para o próximo ciclo.
* **Memória Persistente (Anti-Amnésia):** Utiliza um "Cérebro JSON" (`memoria_bot.json`) para salvar o estado da operação. Se a internet cair ou o script for reiniciado, ele lembra exatamente o seu Preço Médio e quantos lotes já comprou.
* **Filtro "Anti-Fantasmas":** O código avalia apenas o fechamento consolidado das velas, impedindo que oscilações momentâneas acionem ordens erradas.
* **Notificações no Telegram:** Envia relatórios em tempo real diretamente para o seu celular sobre compras executadas, lucros obtidos e um "bip" de hora em hora informando o status do mercado.
* **Proteção de Taxas (Dust):** Verifica o saldo exato de moedas na carteira antes de vender, evitando erros de "Saldo Insuficiente" causados pelas taxas da corretora.
* **Auditoria em CSV:** Registra todas as entradas e saídas em um extrato detalhado (`registro_operacoes.csv`).

## 🛠️ Tecnologias e Bibliotecas

* **Python 3.x**
* `pandas` (Manipulação de dados e DataFrames)
* `ccxt` ou biblioteca nativa da Binance (Conexão com a API da corretora)
* `requests` (Comunicação com a API do Telegram)
* `math`, `json`, `time`, `datetime` (Bibliotecas nativas do Python)

## ⚙️ Configuração e Instalação

**1. Clone o repositório ou baixe os arquivos**
Coloque todos os arquivos (`main.py`, `config.py`, `indicadores.py`, etc.) em uma mesma pasta.

**2. Instale as dependências**
Abra o terminal na pasta do projeto e rode:
```bash
pip install pandas requests ccxt
