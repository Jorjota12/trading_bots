# 🤖 Sistema de Trading Bots — Crypto Scalping (Paper Trading)

Tres bots de trading completamente funcionales operando en **Binance Testnet** (dinero simulado)
con un sistema de comparación de rendimiento en tiempo real.

---

## 📁 Estructura del proyecto

```
trading_bots/
├── .env                  ← Tus API keys (créalo desde .env.example)
├── config.py             ← Parámetros globales (capital, riesgo, timeframes...)
├── exchange.py           ← Conexión a Binance Testnet via ccxt
├── risk_manager.py       ← Cálculo de tamaño de posición, SL y TP dinámicos
├── logger.py             ← Registro de todas las operaciones en CSV
├── bot1_trend.py         ← Bot 1: Trend Follower (EMA + MACD + ATR)
├── bot2_meanrevert.py    ← Bot 2: Mean Reversion (RSI + Bollinger + Stochastic)
├── bot3_momentum.py      ← Bot 3: Momentum Breakout (VWAP + EMA + Volumen)
├── comparator.py         ← Dashboard de métricas y ranking
└── main.py               ← Lanzador de los 3 bots en paralelo
```

---

## 🚀 Instalación

### 1. Dependencias
```bash
pip install ccxt pandas numpy python-dotenv tabulate colorama
```

### 2. Conseguir API Keys de Binance Testnet
1. Ve a https://testnet.binance.vision/
2. Inicia sesión con GitHub
3. Genera un par de API Key / Secret
4. Copia `.env.example` a `.env` y pega tus credenciales

### 3. (Opcional) Ajusta los parámetros en `config.py`
```python
SYMBOL          = "BTC/USDT"   # Par a operar
CAPITAL_PER_BOT = 1000.0       # USDT por bot
RISK_PER_TRADE  = 0.01         # 1% de riesgo por operación
```

---

## ▶️ Uso

### Lanzar los 3 bots a la vez
```bash
python main.py
```

### Lanzar solo un bot concreto
```bash
python main.py --bot 1    # Solo Trend Follower
python main.py --bot 2    # Solo Mean Reversion
python main.py --bot 3    # Solo Momentum
```

### Ver el dashboard de comparación en cualquier momento
```bash
python main.py --compare
# o directamente:
python comparator.py
```

### Detener los bots
Pulsa `Ctrl+C` — se generará automáticamente el reporte final.

---

## 🤖 Los 3 bots explicados

### Bot 1 — Trend Follower (`bot1_trend.py`)
| | |
|---|---|
| **Filosofía** | La tendencia es tu amiga |
| **Indicadores** | EMA 9/21/50 + MACD + ATR |
| **Timeframe** | 5 minutos |
| **Entra cuando** | EMA9 > EMA21 > EMA50 (o inverso) + cruce MACD |
| **Sale cuando** | SL / TP por ATR |
| **Mejor en** | Mercados con tendencia clara |

### Bot 2 — Mean Reversion (`bot2_meanrevert.py`)
| | |
|---|---|
| **Filosofía** | Los precios extremos vuelven a la media |
| **Indicadores** | RSI + Bandas de Bollinger + Stochastic + ATR |
| **Timeframe** | 3 minutos |
| **Entra cuando** | Precio toca banda Bollinger + RSI extremo + cruce Stochastic |
| **Sale cuando** | Precio vuelve a la media de Bollinger, o SL/TP por ATR |
| **Mejor en** | Mercados laterales / en rango |

### Bot 3 — Momentum Breakout (`bot3_momentum.py`)
| | |
|---|---|
| **Filosofía** | El momentum se mantiene |
| **Indicadores** | VWAP + EMA 9 + Ratio de Volumen + ATR |
| **Timeframe** | 1 minuto |
| **Entra cuando** | Precio > VWAP y EMA9 + spike de volumen (1.5× media) |
| **Sale cuando** | SL/TP por ATR o inversión de señal |
| **Mejor en** | Breakouts, noticias, alta volatilidad |

---

## 📊 Métricas de comparación

El dashboard de `comparator.py` calcula para cada bot:

| Métrica | Qué mide | Bueno si... |
|---|---|---|
| **Win Rate** | % de operaciones ganadoras | > 50% |
| **Profit Factor** | Ganancias totales / Pérdidas totales | > 1.5 |
| **Expectancy** | Ganancia media esperada por trade | > 0 |
| **Max Drawdown** | Peor racha de pérdidas | Lo más pequeño posible |
| **Sharpe Ratio** | Rentabilidad ajustada al riesgo | > 1.0 |

---

## ⚙️ Gestión de riesgo

Todos los bots comparten la misma lógica de riesgo en `risk_manager.py`:

- **Stop Loss dinámico**: `entrada ± (ATR × 1.5)` — se adapta a la volatilidad actual
- **Take Profit dinámico**: `entrada ± (ATR × 3.0)` — ratio riesgo/beneficio de 1:2
- **Tamaño de posición**: calculado para que si salta el SL, se pierda exactamente el 1% del capital

---

## 📈 Flujo de datos

```
Binance Testnet
      │
      ▼
 fetch_ohlcv()          ← velas OHLCV en el timeframe del bot
      │
      ▼
compute_indicators()    ← calcula EMA, MACD, RSI, Bollinger, etc.
      │
      ▼
get_signal()            ← decide si comprar, vender o esperar
      │
      ▼
risk_manager            ← calcula tamaño, SL y TP
      │
      ▼
log_trade()             ← guarda el trade en trades_log.csv
      │
      ▼
comparator.py           ← calcula métricas y muestra el ranking
```

---

## ⚠️ Advertencias

- Este sistema opera en **Binance Testnet** con dinero **simulado**. No hay riesgo real.
- Antes de pasar a dinero real, evalúa al menos **100 trades** por bot.
- El rendimiento en paper trading no garantiza resultados iguales en live trading.
- Nunca arriesgues dinero que no puedas permitirte perder.
