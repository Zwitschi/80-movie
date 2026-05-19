CREATE TABLE IF NOT EXISTS bot_mileage_tier (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id         BIGINT NOT NULL,
    name             TEXT NOT NULL,
    points_required  INTEGER NOT NULL,
    role_id          BIGINT,
    sort_order       INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bot_mileage_tier_points_required_check CHECK (points_required >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_mileage_tier_guild_name
    ON bot_mileage_tier (guild_id, name);

CREATE INDEX IF NOT EXISTS idx_bot_mileage_tier_threshold
    ON bot_mileage_tier (guild_id, points_required DESC, sort_order ASC);

CREATE TABLE IF NOT EXISTS bot_mileage_total (
    guild_id          BIGINT NOT NULL,
    discord_user_id   TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    total_points      INTEGER NOT NULL DEFAULT 0,
    current_tier_id   UUID,
    current_tier_name TEXT,
    last_event_id     UUID,
    last_event_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, discord_user_id),
    CONSTRAINT bot_mileage_total_current_tier_fkey
        FOREIGN KEY (current_tier_id)
        REFERENCES bot_mileage_tier(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bot_mileage_total_points
    ON bot_mileage_total (guild_id, total_points DESC, last_event_at DESC);

CREATE TABLE IF NOT EXISTS bot_mileage_event (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id          BIGINT NOT NULL,
    discord_user_id   TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    points_delta      INTEGER NOT NULL,
    reason            TEXT NOT NULL DEFAULT '',
    actor_user_id     TEXT,
    correlation_id    TEXT,
    reversed_event_id UUID REFERENCES bot_mileage_event(id) ON DELETE RESTRICT,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_mileage_event_reversal_once
    ON bot_mileage_event (reversed_event_id)
    WHERE reversed_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bot_mileage_event_user_created_at
    ON bot_mileage_event (guild_id, discord_user_id, created_at DESC, id DESC);