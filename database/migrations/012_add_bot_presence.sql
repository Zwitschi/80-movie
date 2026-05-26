-- Bot worker presence heartbeat table
-- Updated every ~60s by the bot worker to signal health
CREATE TABLE IF NOT EXISTS bot_presence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id       TEXT NOT NULL DEFAULT 'default',
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    state           TEXT NOT NULL DEFAULT 'running',
    metadata        JSONB DEFAULT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_presence_worker ON bot_presence(worker_id);
CREATE INDEX IF NOT EXISTS idx_bot_presence_last_seen ON bot_presence(last_seen_at DESC);