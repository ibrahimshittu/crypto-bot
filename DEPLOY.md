# Cloud Deployment Guide

Everything runs in the cloud from the start:

| Piece | Provider | Why |
|-------|----------|-----|
| **Postgres / time-series** | **Timescale Cloud** | Managed **TimescaleDB** by the team that builds it — native hypertables, compression, continuous aggregates. Best-in-class for OHLCV/funding + backtesting. |
| **Redis** | **Upstash** | Serverless, TLS (`rediss://`), generous free tier. (Upstash has **no** Postgres.) |
| **App (API + trading loop)** | **Fly.io** | Always-on container. The engine runs a persistent background loop, so a serverless function host (Vercel/Lambda) will **not** work. |

> **Why Timescale Cloud over Neon/Supabase:** those don't support TimescaleDB
> hypertables. Our schema auto-detects TimescaleDB and promotes `ohlcv`/`funding_rate`
> to hypertables when it's present — so on Timescale Cloud you get true time-series
> storage with **zero code changes**. (Neon still works as a cheaper fallback; it just
> stays plain Postgres.)

> The app needs an **always-on** host because the trading engine is a continuous
> asyncio loop, not a request/response handler. `auto_stop_machines = false` in
> `fly.toml` keeps it alive.

---

## 1. Redis — Upstash (2 min)

1. Sign up at <https://upstash.com> → **Create Database** → Redis.
2. Pick a region near your app region; enable **TLS** (default).
3. Copy the **`rediss://...`** connection URL (the TLS one, port usually 6379).
4. That becomes `REDIS_URL`.

## 2. TimescaleDB — Timescale Cloud (3 min)  ← recommended

1. Sign up at <https://console.cloud.timescale.com> (free trial, then usage-based).
2. **Create service** → *Time Series and Analytics* (this is the TimescaleDB engine).
   Pick a region near your Fly app region.
3. On creation you get credentials **once** — save the password. Note the host
   (`xxxx.tsdb.cloud.timescale.com`), port (often `5432` or a pooled port), user
   (`tsdbadmin`), and database (`tsdb`).
4. Build the URL (TLS is required):
   ```
   postgresql://tsdbadmin:PASSWORD@xxxx.tsdb.cloud.timescale.com:5432/tsdb?sslmode=require
   ```
   That becomes `DATABASE_URL`. (You can create a `crypto_bot` database instead of using
   `tsdb` if you prefer — just match the URL.)
5. Load the schema — TimescaleDB is pre-installed, so this creates **hypertables**
   automatically:
   ```bash
   psql "$DATABASE_URL" -f scripts/db_init.sql
   ```
   (Or skip it — the app calls `init_schema()` on first DB use.)

> **Cheaper fallback (no TimescaleDB):** Neon (<https://neon.tech>) — copy the *pooled*
> `?sslmode=require` connection string. The schema falls back to plain Postgres + indexes.

## 3. LLM — OpenRouter (1 min)

1. Get one key at <https://openrouter.ai/keys>.
2. That becomes `OPENROUTER_API_KEY`. One key covers many model providers.

## 4. Bybit demo keys

Create **demo** API keys from the Bybit **mainnet demo-trading** page (not testnet).
These become `BYBIT_API_KEY` / `BYBIT_API_SECRET`. Keep `TRADING_ENV=demo`.

---

## 5. Deploy the app to Fly.io

```bash
# install flyctl: https://fly.io/docs/flyctl/install/
fly auth login

# first time: create the app from fly.toml (don't deploy yet)
fly launch --no-deploy --copy-config --name crypto-bot-<you>

# set ALL secrets (never commit these). Paste the URLs/keys from steps 1–4:
fly secrets set \
  TRADING_ENV=demo \
  AUTO_START=true \
  BYBIT_API_KEY=...        BYBIT_API_SECRET=... \
  OPENROUTER_API_KEY=...   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1 \
  LLM_MODEL=minimax/minimax-m3 \
  DATABASE_URL='postgresql://...-pooler...neon.tech/crypto_bot?sslmode=require' \
  REDIS_URL='rediss://default:...@...upstash.io:6379' \
  CRYPTOPANIC_API_KEY= LOGFIRE_TOKEN=

# deploy
fly deploy
```

## 6. Verify the cloud wiring

```bash
fly open                       # opens https://<app>.fly.dev
curl https://<app>.fly.dev/health        # {"status":"ok","env":"demo","running":true}
curl https://<app>.fly.dev/health/deps   # {"postgres":true,"redis":true}  ← confirms cloud DB+Redis
curl https://<app>.fly.dev/cycles        # recent trading-cycle decisions (engine auto-started)
fly logs                                 # watch the engine loop run
```

If `/health/deps` shows an error string instead of `true`, the corresponding
`DATABASE_URL` / `REDIS_URL` secret is wrong — fix and `fly deploy` again.

---

## Alternative: Railway (one dashboard)

If you'd rather keep everything on one platform:
1. New project → add **Postgres** and **Redis** plugins (Railway provisions both).
2. Add a service from this repo (it auto-detects the `Dockerfile`).
3. In the service **Variables**, reference the plugins: `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
   `REDIS_URL=${{Redis.REDIS_URL}}`, plus the Bybit + OpenRouter secrets and `AUTO_START=true`.
4. Railway's Postgres has no TimescaleDB — fine, the schema falls back to plain tables.

---

## Going live (later, deliberately)

Only after demo proves out:
1. Create **live** Bybit keys; `fly secrets set TRADING_ENV=live BYBIT_API_KEY=... BYBIT_API_SECRET=...`.
2. Leave the auto-whitelist empty so **every** live order waits for your approval
   (`GET /orders/pending` → `POST /orders/approve`).
3. Graduate a strategy to auto only once you trust it, by adding it to the workflow whitelist.
