CREATE TABLE IF NOT EXISTS bot_syndication_source (
    source_key          TEXT PRIMARY KEY,
    is_enabled          BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_syndication_checkpoint (
    source_key          TEXT PRIMARY KEY REFERENCES bot_syndication_source(source_key) ON DELETE CASCADE,
    checkpoint          TEXT,
    last_polled_at      TIMESTAMPTZ,
    last_succeeded_at   TIMESTAMPTZ,
    last_failed_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_syndication_source_updated_at'
    ) THEN
        CREATE TRIGGER bot_syndication_source_updated_at
            BEFORE UPDATE ON bot_syndication_source
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_syndication_checkpoint_updated_at'
    ) THEN
        CREATE TRIGGER bot_syndication_checkpoint_updated_at
            BEFORE UPDATE ON bot_syndication_checkpoint
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;