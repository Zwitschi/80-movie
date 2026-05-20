-- Add onboarding configuration to bot_guild_config
ALTER TABLE bot_guild_config
    ADD COLUMN onboarding_welcome_copy TEXT NOT NULL DEFAULT '',
    ADD COLUMN onboarding_starter_channels BIGINT[] NOT NULL DEFAULT '{}';

-- Table for tracking onboarding completion/status per user
CREATE TABLE bot_onboarding_user_state (
    guild_id             BIGINT NOT NULL REFERENCES bot_guild_config(guild_id) ON DELETE CASCADE,
    discord_user_id      TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'in_progress', 'completed'
    joined_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    onboarded_at         TIMESTAMPTZ,
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, discord_user_id)
);

CREATE INDEX idx_bot_onboarding_user_status ON bot_onboarding_user_state(guild_id, status);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'bot_onboarding_user_state_updated_at'
    ) THEN
        CREATE TRIGGER bot_onboarding_user_state_updated_at
            BEFORE UPDATE ON bot_onboarding_user_state
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
    END IF;
END;
$$;
