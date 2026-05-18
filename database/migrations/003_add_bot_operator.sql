CREATE TABLE IF NOT EXISTS bot_operator (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_user_id     TEXT NOT NULL UNIQUE,
    username            TEXT,
    global_name         TEXT,
    avatar_url          TEXT,
    scopes              TEXT[] NOT NULL DEFAULT ARRAY['ops.read']::TEXT[],
    is_active           BOOLEAN NOT NULL DEFAULT true,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_operator_active ON bot_operator(is_active);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_operator_updated_at'
    ) THEN
        CREATE TRIGGER bot_operator_updated_at
            BEFORE UPDATE ON bot_operator
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;