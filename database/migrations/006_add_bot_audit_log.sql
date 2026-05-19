CREATE TABLE IF NOT EXISTS bot_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id       TEXT,
    actor_session_id    TEXT,
    action_key          TEXT NOT NULL,
    target_type         TEXT NOT NULL,
    target_key          TEXT NOT NULL,
    request_id          TEXT,
    before_state        JSONB,
    after_state         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_audit_log_created_at
    ON bot_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bot_audit_log_target
    ON bot_audit_log (target_type, target_key, created_at DESC);