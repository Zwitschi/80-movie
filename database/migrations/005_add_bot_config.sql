CREATE TABLE IF NOT EXISTS bot_guild_config (
    guild_id             BIGINT PRIMARY KEY,
    is_active            BOOLEAN NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_guild_config_single_active
    ON bot_guild_config (is_active)
    WHERE is_active = true;

CREATE TABLE IF NOT EXISTS bot_channel_binding (
    guild_id             BIGINT NOT NULL REFERENCES bot_guild_config(guild_id) ON DELETE CASCADE,
    binding_key          TEXT NOT NULL,
    channel_id           BIGINT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, binding_key)
);

CREATE TABLE IF NOT EXISTS bot_role_binding (
    guild_id             BIGINT NOT NULL REFERENCES bot_guild_config(guild_id) ON DELETE CASCADE,
    binding_key          TEXT NOT NULL,
    role_id              BIGINT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, binding_key)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_guild_config_updated_at'
    ) THEN
        CREATE TRIGGER bot_guild_config_updated_at
            BEFORE UPDATE ON bot_guild_config
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_channel_binding_updated_at'
    ) THEN
        CREATE TRIGGER bot_channel_binding_updated_at
            BEFORE UPDATE ON bot_channel_binding
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_role_binding_updated_at'
    ) THEN
        CREATE TRIGGER bot_role_binding_updated_at
            BEFORE UPDATE ON bot_role_binding
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;