-- Migration 009: Add bot onboarding config and event tables

CREATE TABLE IF NOT EXISTS bot_onboarding_config (
    guild_id                BIGINT          PRIMARY KEY,
    welcome_copy            TEXT            NOT NULL DEFAULT '',
    starter_channel_ids     BIGINT[]        NOT NULL DEFAULT ARRAY[]::BIGINT[],
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_onboarding_role_binding (
    id                      SERIAL          PRIMARY KEY,
    guild_id                BIGINT          NOT NULL REFERENCES bot_onboarding_config(guild_id) ON DELETE CASCADE,
    binding_key             TEXT            NOT NULL,
    role_id                 BIGINT          NOT NULL,
    label                   TEXT            NOT NULL DEFAULT '',
    UNIQUE (guild_id, binding_key)
);

CREATE TABLE IF NOT EXISTS bot_onboarding_event (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id                BIGINT          NOT NULL,
    discord_user_id         TEXT            NOT NULL,
    display_name            TEXT            NOT NULL DEFAULT '',
    event_type              TEXT            NOT NULL,
    role_id                 BIGINT,
    role_binding_key        TEXT,
    idempotency_key         TEXT            NOT NULL UNIQUE,
    actor_user_id           TEXT,
    payload                 JSONB           NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bot_onboarding_event_guild_id_idx
    ON bot_onboarding_event (guild_id, created_at DESC);

CREATE INDEX IF NOT EXISTS bot_onboarding_event_user_idx
    ON bot_onboarding_event (guild_id, discord_user_id, created_at DESC);
