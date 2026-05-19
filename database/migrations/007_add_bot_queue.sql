CREATE TABLE IF NOT EXISTS bot_queue (
    queue_id         TEXT PRIMARY KEY,
    guild_id         BIGINT NOT NULL,
    label            TEXT NOT NULL,
    is_paused        BOOLEAN NOT NULL DEFAULT false,
    paused_reason    TEXT NOT NULL DEFAULT '',
    active_entry_id  UUID,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_queue_entry (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id         TEXT NOT NULL REFERENCES bot_queue(queue_id) ON DELETE CASCADE,
    discord_user_id  TEXT NOT NULL,
    display_name     TEXT NOT NULL,
    state            TEXT NOT NULL,
    position         INTEGER NOT NULL,
    note             TEXT NOT NULL DEFAULT '',
    joined_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bot_queue_entry_state_check CHECK (state IN ('active', 'waiting'))
);

ALTER TABLE bot_queue
    ADD CONSTRAINT bot_queue_active_entry_fkey
    FOREIGN KEY (active_entry_id)
    REFERENCES bot_queue_entry(id)
    ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_queue_one_active_entry
    ON bot_queue_entry (queue_id, state)
    WHERE state = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_queue_user_current_entry
    ON bot_queue_entry (queue_id, discord_user_id);

CREATE INDEX IF NOT EXISTS idx_bot_queue_entry_order
    ON bot_queue_entry (queue_id, position, joined_at);

CREATE TABLE IF NOT EXISTS bot_queue_event (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id         TEXT NOT NULL REFERENCES bot_queue(queue_id) ON DELETE CASCADE,
    entry_id         UUID,
    event_type       TEXT NOT NULL,
    actor_user_id    TEXT,
    payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_queue_event_queue_created_at
    ON bot_queue_event (queue_id, created_at DESC, id DESC);