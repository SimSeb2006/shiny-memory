
import os
import time
import requests

# ── Configurações ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("CHAT_ID")
AV_API_KEY     = os.environ.get("AV_API_KEY")
INTERVALO_MIN  = 15  # minutos entre verificações

ultimo_sinal = None  # guarda o último sinal para não repetir

# ── Funções de indicadores ─────────────────────────────────────

def def obter_precos():
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD"
        f"&interval=5min&outputsize=compact&apikey={AV_API_KEY}"
    )
    r = requests.get(url, timeout=10)
    data = r.json()

    # Log para ver o que a API diz (ajuda muito a debugar no Railway)
    if "Error Message" in data:
        print(f"Erro na API: {data['Error Message']}")
        return []
    if "Note" in data:
        print("Aviso: Limite de chamadas da Alpha Vantage atingido!")
        return []

    series = data.get("Time Series FX (5min)", {})
    
    if not series:
        print("A API não devolveu dados (pode ser fim de semana ou mercado fechado).")
        return []

    # Vamos buscar as velas e converter para float
    precos = [float(v["4. close"]) for v in list(series.values())]
    
    # Se houver dados, ele traz os 100 últimos. Vamos garantir que temos os 27.
    print(f"Velas recebidas: {len(precos)}")
    
    return list(reversed(precos)) # Do mais antigo para o mais recente

def calcular_ema(precos, periodo):
    k = 2 / (periodo + 1)
    ema = precos[0]
    for p in precos[1:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 5)

def calcular_rsi(precos, periodo=14):
    if len(precos) < periodo + 1:
        return 50
    ganhos, perdas = 0, 0
    for i in range(len(precos) - periodo, len(precos)):
        diff = precos[i] - precos[i-1]
        if diff > 0:
            ganhos += diff
        else:
            perdas -= diff
    avg_g = ganhos / periodo
    avg_l = perdas / periodo
    if avg_l == 0:
        return 100
    rs = avg_g / avg_l
    return round(100 - (100 / (1 + rs)), 1)

def calcular_macd(precos):
    fast = calcular_ema(precos[-12:], 12)
    slow = calcular_ema(precos[-26:], 26)
    return round(fast - slow, 5)

def calcular_sinal(rsi_val, ema9, ema21, macd_val):
    bull, bear = 0, 0
    detalhes = []

    if rsi_val < 45:
        bull += 1
        detalhes.append(f"RSI: {rsi_val} 📉 Oversold")
    elif rsi_val > 60:
        bear += 1
        detalhes.append(f"RSI: {rsi_val} 📈 Overbought")
    else:
        detalhes.append(f"RSI: {rsi_val} ➡️ Neutro")

    if ema9 > ema21:
        bull += 1
        detalhes.append(f"EMA 9/21: ↑ Bullish")
    else:
        bear += 1
        detalhes.append(f"EMA 9/21: ↓ Bearish")

    if macd_val > 0:
        bull += 1
        detalhes.append(f"MACD: +{macd_val} ↑ Bullish")
    else:
        bear += 1
        detalhes.append(f"MACD: {macd_val} ↓ Bearish")

    if bull >= 2:
        return "COMPRAR", detalhes
    elif bear >= 2:
        return "VENDER", detalhes
    else:
        return "AGUARDAR", detalhes

# ── Enviar mensagem Telegram ───────────────────────────────────

def enviar_mensagem(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"})

# ── Loop principal ─────────────────────────────────────────────

def verificar_e_enviar():
    global ultimo_sinal
    try:
        precos = obter_precos()
        if len(precos) < 27:
            print("Dados insuficientes")
            return

        rsi_val = calcular_rsi(precos)
        ema9    = calcular_ema(precos, 9)
        ema21   = calcular_ema(precos, 21)
        macd_val = calcular_macd(precos)
        sinal, detalhes = calcular_sinal(rsi_val, ema9, ema21, macd_val)

        # Só envia se for COMPRAR ou VENDER (e diferente do último sinal)
        if sinal in ("COMPRAR", "VENDER") and sinal != ultimo_sinal:
            emoji = "🟢" if sinal == "COMPRAR" else "🔴"
            msg = (
                f"{emoji} <b>EUR/USD — {sinal}</b>\n\n"
                + "\n".join(detalhes)
                + f"\n\nTimeframe: 5m"
            )
            enviar_mensagem(msg)
            ultimo_sinal = sinal
            print(f"Sinal enviado: {sinal}")
        else:
            print(f"Sinal atual: {sinal} — sem alteração, não enviado")

    except Exception as e:
        print(f"Erro: {e}")

print("Bot iniciado. A verificar sinais...")
enviar_mensagem("🚀 O bot foi ligado no Railway e está a monitorizar o EUR/USD!")
while True:
    verificar_e_enviar()
    time.sleep(INTERVALO_MIN * 60)

