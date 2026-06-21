# crypto_bot — Autonomous AI Crypto Trading Service

An intelligent, self-improving crypto trading system on **Bybit** (spot + perpetuals),
built with **Pydantic AI** (multi-agent reasoning) and **FastAPI** (control plane).

> **Status:** under construction. Runs on Bybit **demo** (paper) by default. No real
> money is touched until you explicitly set `TRADING_ENV=live` *and* approve/whitelist
> trades.

## Design in one paragraph

LLM agents do what LLMs are good at — reading news/sentiment, synthesizing market
context, picking which *validated* strategy fits the current regime/session, and
writing post-trade reflections. A deterministic core does the math: strategy signals,
rigorous backtest validation (triple-barrier + purged CV + **deflated Sharpe**),
position sizing from **live capital**, risk circuit-breakers, and order execution.
This split exists because the research is blunt that LLMs are weak as the raw *signal*
(see StockBench, arXiv 2510.02209) — so we use them as orchestrators, not oracles.

## Key safety properties

- **Capital-aware sizing**: every order is a fraction of *current equity* (read live
  from Bybit), never a fixed dollar amount. Caps on per-trade risk, position size,
  leverage, and order-book slippage.
- **Validation gate**: no strategy can risk money until it survives López de Prado-style
  validation with costs modeled. Overfit backtests are rejected by design.
- **Phased rollout**: demo → live-with-human-approval → graduated auto-execution.
- **Circuit breakers**: daily loss halt, drawdown ladder, kill switch.

## Layout

| Path | What |
|------|------|
| `knowledge/` | The domain "skills": strategies, sessions, microstructure, risk, execution, validation, data sources. |
| `core/` | Deterministic engines: strategies, validation, screener, risk, execution, sessions. |
| `agents/` | Pydantic AI agents + orchestrator. |
| `data/` | Market / news / sentiment / on-chain ingestion + DB. |
| `app/` | FastAPI control plane + WebSocket feed. |
| `memory/` | Trade journal + reflection store (self-improvement). |
| `tests/` | Test suite. |

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # runtime deps
cp .env.example .env                      # then fill in your keys (see below)
```

Minimum keys in `.env` to do anything useful:

| Key | Why |
|-----|-----|
| `OPENROUTER_API_KEY` | **Required** — the strategy reasoner is LLM-first (`LLM_MODEL`, default `minimax/minimax-m3`) |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Bybit **demo** keys (mainnet demo-trading page) |
| `DATABASE_URL` | Postgres/TimescaleDB (Timescale Cloud or local) |
| `REDIS_URL` | Redis (Upstash `rediss://` or local) |
| `EXA_API_KEY` | News/sentiment (optional; enables the Exa sentiment reasoner) |

## Running locally — without Docker

You don't need Docker if you point `DATABASE_URL`/`REDIS_URL` at cloud datastores
(Timescale Cloud + Upstash). The app's background trading loop is the entry point — run it
with uvicorn (note the module is **`app.main:app`**):

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```

Then drive it over HTTP:

```bash
curl localhost:8080/health           # {"status":"ok","env":"demo","running":false}
curl localhost:8080/health/deps      # {"postgres":true,"redis":true}  ← verifies datastores
curl -X POST localhost:8080/engine/run-once   # run ONE scan→signal→risk→order cycle
curl -X POST localhost:8080/engine/start      # start the continuous loop
curl localhost:8080/cycles           # recent cycle decisions
curl -X POST localhost:8080/research/BTCUSDT  # on-demand Exa deep-dive (needs EXA_API_KEY)
```

Set `AUTO_START=true` in `.env` to start the loop automatically on boot (used in the cloud).

## How a trade is taken (and who fires it)

The LLM's `StrategyDecision` is a **suggestion**, not an order. Every suggestion passes
through deterministic gates before anything trades:

```
LLM decision  →  Orchestrator (skip if declined / target 0)
              →  RISK ENGINE  (sizes from LIVE equity, clamps leverage, vetoes on
                               circuit-breaker / depth / correlation / exposure — the
                               LLM cannot override this)
              →  Rounding     (qty → lot step, price → tick; skip if below min)
              →  set_leverage (applies the risk-approved leverage)
              →  ORDER WORKFLOW → Bybit
```

**Who fires it** depends on the environment:

| | Behaviour |
|--|--|
| **demo / testnet** | Orders **auto-fill** on the paper account (no real money). |
| **live**, strategy not whitelisted | Order is held **pending your approval** (`GET /orders/pending` → `POST /orders/approve`). |
| **live**, strategy whitelisted | Order **auto-submits**. |

### Two different "auto" settings — don't confuse them

- **`AUTO_START`** — whether the engine *loop* starts on boot. It only controls *scanning
  and deciding*; it does **not** place real orders by itself. `false` = idle until you
  `POST /engine/start`; `true` = the loop runs on boot (used in the cloud).
- **auto-submit whitelist** — on **live**, whether a strategy's orders skip your approval.
  This is the only setting that lets a real order fire without you. Empty by default, so
  on live every order waits for you.

So on **demo** nothing is at risk; on **live**, real money only moves when *you* approve an
order — unless you deliberately whitelist a strategy.

### Interactive API docs (easiest way to use it)

With the app running, open **<http://localhost:8080/docs>** — FastAPI auto-generates a
Swagger UI where you can call every endpoint from the browser (no curl needed).
`/redoc` is the read-only version.

### API reference

You operate the bot entirely over HTTP. The engine runs a background loop; these
endpoints start/stop it, inspect state, and approve live orders.

| Method & path | What it does |
|---------------|--------------|
| `GET /health` | Liveness + env + whether the loop is running |
| `GET /health/deps` | Pings Postgres + Redis (`{"postgres":true,"redis":true}`) |
| `POST /engine/run-once` | Run **one** cycle (scan → signal → risk → order) and return the decision |
| `POST /engine/start` | Start the continuous loop |
| `POST /engine/stop` | Stop the loop |
| `GET /cycles?limit=20` | Recent cycle decisions (candidates, signals, orders, notes) |
| `GET /balance` | Live account equity/available |
| `GET /positions` | Open positions |
| `GET /orders/pending` | Orders awaiting approval (live mode) |
| `POST /orders/approve` | Approve a pending order — body `{"ticket_id": 1}` |
| `POST /orders/reject` | Reject a pending order — body `{"ticket_id": 1}` |
| `POST /research/{symbol}` | On-demand Exa deep-dive report (needs `EXA_API_KEY`) |
| `WS /ws/cycles` | WebSocket stream of cycle decisions as they happen |

Typical first run (demo):

```bash
uvicorn app.main:app --port 8080 &
curl localhost:8080/health/deps                 # confirm datastores
curl -X POST localhost:8080/engine/run-once     # one cycle, see what it would do
curl localhost:8080/cycles | jq                 # inspect the decision + notes
curl localhost:8080/positions | jq              # what it opened (demo paper fills)
```

Live mode (`TRADING_ENV=live`): orders don't fire until you approve them —
`GET /orders/pending` → `POST /orders/approve {"ticket_id": N}`.

Stream cycles live:

```bash
# any WS client, e.g. websocat
websocat ws://localhost:8080/ws/cycles
```

### With Docker (local datastores instead of cloud)

```bash
docker compose up -d                 # TimescaleDB + Redis on localhost
# set DATABASE_URL=postgresql://crypto:crypto@localhost:5432/crypto_bot
#     REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --port 8080
```

## Tests

```bash
pip install -r requirements-dev.txt   # adds pytest, ruff, mypy + research/TA libs
pytest -q
```

## Optional dependencies (research / TA)

The runtime (`requirements.txt`) is everything needed to **run** the bot. The heavier
research/TA libraries are split into `requirements-dev.txt` (also the `[research]` extra in
`pyproject.toml`) because they're only needed for deeper backtesting work, not live trading:

| Library | Use |
|---------|-----|
| `vectorbt` | Fast vectorized backtests / parameter sweeps over the strategy library |
| `statsmodels` | Cointegration (Engle-Granger/Johansen) + OU fits for stat-arb pairs |
| `pandas-ta` | Extra technical indicators beyond the built-in ones |

Install them only when you want to do research:

```bash
pip install -r requirements-dev.txt        # or:  pip install -e ".[research]"
```

They're imported lazily where used, so the core app and tests run fine without them.
Put exploratory backtests in `backtests/` and import the strategy classes from
`core/strategies/` + the gate from `core/validation/`.

## Trading style (small capital)

Primary: **swing trading** (hours–days) on momentum / mean-reversion / event signals.
Secondary: **session-aware intraday** around the London/NY overlap (13:00–17:00 UTC).
Carry sleeve: **funding-rate / cash-and-carry basis** when perps margin allows.
Excluded (not viable at small size/infra): HFT, market-making, latency/triangular arb.
