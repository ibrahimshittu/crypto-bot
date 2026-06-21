-- Database bootstrap: works on ANY managed Postgres (Neon, Supabase, RDS) AND on
-- TimescaleDB. Hypertables are created only if the timescaledb extension is available,
-- otherwise the same tables work as plain Postgres with good indexes.
-- Safe to run repeatedly (idempotent).

-- ── Optional TimescaleDB extension ───────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
        CREATE EXTENSION IF NOT EXISTS timescaledb;
    END IF;
END$$;

-- ── Time-series: OHLCV candles ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv (
    time      TIMESTAMPTZ      NOT NULL,
    symbol    TEXT             NOT NULL,
    category  TEXT             NOT NULL,   -- spot | linear
    interval  TEXT             NOT NULL,   -- 1, 5, 15, 60, D ...
    open      DOUBLE PRECISION NOT NULL,
    high      DOUBLE PRECISION NOT NULL,
    low       DOUBLE PRECISION NOT NULL,
    close     DOUBLE PRECISION NOT NULL,
    volume    DOUBLE PRECISION NOT NULL,
    turnover  DOUBLE PRECISION,
    PRIMARY KEY (symbol, category, interval, time)
);

-- ── Time-series: funding rates (perps) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS funding_rate (
    time          TIMESTAMPTZ      NOT NULL,
    symbol        TEXT             NOT NULL,
    funding_rate  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (symbol, time)
);

-- Promote to TimescaleDB hypertables only if the extension is installed.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('ohlcv', 'time', if_not_exists => TRUE);
        PERFORM create_hypertable('funding_rate', 'time', if_not_exists => TRUE);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time ON funding_rate (symbol, time DESC);

-- ── Relational state ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    env           TEXT        NOT NULL,        -- demo | testnet | live
    symbol        TEXT        NOT NULL,
    category      TEXT        NOT NULL,
    side          TEXT        NOT NULL,        -- Buy | Sell
    order_type    TEXT        NOT NULL,        -- Market | Limit
    qty           DOUBLE PRECISION NOT NULL,
    price         DOUBLE PRECISION,
    leverage      DOUBLE PRECISION,
    strategy      TEXT,
    status        TEXT NOT NULL DEFAULT 'pending_approval',
    bybit_order_id TEXT,
    meta          JSONB
);

CREATE TABLE IF NOT EXISTS trade_journal (
    id            BIGSERIAL PRIMARY KEY,
    opened_at     TIMESTAMPTZ,
    closed_at     TIMESTAMPTZ DEFAULT now(),
    symbol        TEXT NOT NULL,
    strategy      TEXT,
    session_label TEXT,
    regime        TEXT,
    thesis        TEXT,
    entry_price   DOUBLE PRECISION,
    exit_price    DOUBLE PRECISION,
    qty           DOUBLE PRECISION,
    pnl           DOUBLE PRECISION,
    pnl_pct       DOUBLE PRECISION,
    expected_slippage DOUBLE PRECISION,
    realized_slippage DOUBLE PRECISION,
    meta          JSONB
);

CREATE TABLE IF NOT EXISTS lessons (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    scope       TEXT,
    lesson      TEXT NOT NULL,
    weight      DOUBLE PRECISION DEFAULT 1.0,
    meta        JSONB
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_symbol ON trade_journal (symbol, closed_at DESC);
