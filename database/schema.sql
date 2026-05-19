-- PostgreSQL Schema for Open Mic Odyssey movie site
-- Covers: schema.org entities, dynamic page content, data files
--
-- Conventions:
--   - UUID PKs for all entity tables
--   - JSONB for flexible nested data (sameAs, address, roles arrays)
--   - Timestamptz with timezone awareness
--   - Partial unique indexes where applicable
--   - FK with ON DELETE CASCADE for owned children

-- ============================================================
-- CORE ENTITIES
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- MOVIE (singular: one film per site)
CREATE TABLE movie (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    tagline         TEXT,
    description     TEXT,
    genre           TEXT,
    keywords        TEXT[],
    duration_iso    TEXT,               -- ISO 8601 duration e.g. PT180M
    date_published  DATE,
    in_language     TEXT DEFAULT 'en',
    poster_image    TEXT,
    content_rating  TEXT,
    release_date    TEXT,               -- free-text e.g. "Post-Production"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- release_status (1:1 with movie)
CREATE TABLE movie_release_status (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id        UUID NOT NULL UNIQUE REFERENCES movie(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    headline        TEXT,
    summary         TEXT,
    detail          TEXT
);

-- ORGANIZATION (production company + others)
CREATE TABLE organization (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    url             TEXT,
    same_as         JSONB,              -- array of URLs
    contact_email   TEXT,
    logo            TEXT
);

-- PERSON
CREATE TABLE person (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    job_title       TEXT,
    url             TEXT,
    same_as         JSONB,              -- array of URLs
    credit_note     TEXT,
    roles           TEXT[]              -- e.g. {'Comedian','Security'}
);

-- M:N organization <-> person (membership)
CREATE TABLE organization_member (
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    person_id       UUID NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    PRIMARY KEY (organization_id, person_id)
);

-- video object (trailer) — 1:1 with movie
CREATE TABLE trailer (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id            UUID NOT NULL UNIQUE REFERENCES movie(id) ON DELETE CASCADE,
    production_company_id UUID REFERENCES organization(id),
    name                TEXT NOT NULL,
    description         TEXT,
    url                 TEXT,
    embed_url           TEXT,
    thumbnail_url       TEXT,
    upload_date         TIMESTAMPTZ,
    duration_iso        TEXT,
    encoding_format     TEXT,
    is_family_friendly  BOOLEAN DEFAULT true,
    director_refs       JSONB,          -- [{@id: ...}]
    actor_refs          JSONB
);

-- ============================================================
-- REVIEWS & RATINGS
-- ============================================================

-- REVIEW
CREATE TABLE review (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id        UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    author_name     TEXT NOT NULL,
    author_url      TEXT,
    date_published  DATE,
    name            TEXT,
    review_body     TEXT,
    review_rating   NUMERIC(3,1),       -- 1.0–5.0
    best_rating     NUMERIC(3,1) DEFAULT 5.0,
    worst_rating    NUMERIC(3,1) DEFAULT 1.0
);

CREATE INDEX idx_review_movie ON review(movie_id);

-- AGGREGATE RATING (1:1 with movie)
CREATE TABLE aggregate_rating (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id        UUID NOT NULL UNIQUE REFERENCES movie(id) ON DELETE CASCADE,
    rating_value    NUMERIC(3,1) NOT NULL,
    best_rating     NUMERIC(3,1) DEFAULT 5.0,
    worst_rating    NUMERIC(3,1) DEFAULT 1.0,
    rating_count    INT NOT NULL DEFAULT 0,
    review_count    INT NOT NULL DEFAULT 0
);

-- ============================================================
-- OFFERS & SCREENING EVENTS
-- ============================================================

-- OFFER (generic)
CREATE TABLE offer (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    url             TEXT,
    description     TEXT,
    category        TEXT,
    availability    TEXT,               -- schema.org URL
    price           NUMERIC(10,2),
    price_currency  TEXT DEFAULT 'USD',
    valid_from      DATE,
    UNIQUE(name, url)
);

-- junction: which movie this offer is for
CREATE TABLE movie_offer (
    movie_id    UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    offer_id    UUID NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, offer_id)
);

-- SCREENING EVENT
CREATE TABLE screening_event (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id                UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    description             TEXT,
    start_date              TIMESTAMPTZ,
    end_date                TIMESTAMPTZ,
    event_status            TEXT,       -- schema.org URL
    event_attendance_mode   TEXT,       -- schema.org URL
    video_format            TEXT,
    subtitle_language       TEXT,
    -- embedded location (Place + PostalAddress)
    location_name           TEXT,
    location_url            TEXT,
    location_street_address TEXT,
    location_locality       TEXT,
    location_region         TEXT,
    location_postal_code    TEXT,
    location_country        TEXT
);

CREATE INDEX idx_screening_movie ON screening_event(movie_id);

-- junction: offers specific to a screening
CREATE TABLE screening_offer (
    screening_event_id UUID NOT NULL REFERENCES screening_event(id) ON DELETE CASCADE,
    offer_id           UUID NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    PRIMARY KEY (screening_event_id, offer_id)
);

-- ============================================================
-- FAQ
-- ============================================================

CREATE TABLE faq_item (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id    UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    sort_order  INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_faq_movie ON faq_item(movie_id);

-- ============================================================
-- GALLERY
-- ============================================================

CREATE TABLE gallery_item (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id    UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    category    TEXT,
    image_url   TEXT NOT NULL,
    alt         TEXT,
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_gallery_movie ON gallery_item(movie_id);

-- ============================================================
-- SOCIAL & CONNECT LINKS
-- ============================================================

CREATE TABLE social_link (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

-- connect campaigns
CREATE TABLE connect_campaign (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    status      TEXT,
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

-- connect / campaign channels
CREATE TABLE connect_channel (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    status      TEXT,               -- e.g. 'Primary', 'Support'
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

-- connect page content (patreon/supporter page metadata)
CREATE TABLE connect_page (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    intro               TEXT,
    membership_pitch    TEXT,
    primary_link_label  TEXT,
    primary_link_url    TEXT,
    secondary_link_label TEXT,
    secondary_link_url  TEXT
);

-- ============================================================
-- PATREON / SUPPORTER PAGE
-- ============================================================

CREATE TABLE patreon_benefit (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

CREATE TABLE patreon_tier (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    price       TEXT NOT NULL,       -- display string e.g. "$5 / month"
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
);

-- ============================================================
-- PAGE CONTENT (dynamic CMS per page route)
-- ============================================================

CREATE TABLE page (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_name      TEXT NOT NULL UNIQUE,  -- e.g. 'index', 'film', 'media', 'connect', 'patreon'
    path            TEXT NOT NULL,          -- e.g. '/', '/film', '/connect'
    title           TEXT NOT NULL,          -- meta title
    description     TEXT,                  -- meta description
    keywords        TEXT[],
    -- JSONB for page-specific content blocks (hero, CTAs, synopsis, etc.)
    -- Schema varies per page; stored as JSONB for flexibility
    content         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- JUNCTION: MOVIE <-> PERSON (credits/contributors)
-- ============================================================

CREATE TYPE credit_role AS ENUM ('director', 'producer', 'actor', 'contributor');

CREATE TABLE movie_credit (
    movie_id    UUID NOT NULL REFERENCES movie(id) ON DELETE CASCADE,
    person_id   UUID NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    role        credit_role NOT NULL,
    sort_order  INT NOT NULL DEFAULT 0,
    PRIMARY KEY (movie_id, person_id, role)
);

CREATE INDEX idx_credit_movie ON movie_credit(movie_id);
CREATE INDEX idx_credit_person ON movie_credit(person_id);

-- ============================================================
-- BOT OPERATOR ACCESS
-- ============================================================

CREATE TABLE bot_operator (
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

CREATE INDEX idx_bot_operator_active ON bot_operator(is_active);

-- ============================================================
-- BOT SYNDICATION
-- ============================================================

CREATE TABLE bot_syndication_source (
    source_key          TEXT PRIMARY KEY,
    is_enabled          BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bot_syndication_checkpoint (
    source_key          TEXT PRIMARY KEY REFERENCES bot_syndication_source(source_key) ON DELETE CASCADE,
    checkpoint          TEXT,
    last_polled_at      TIMESTAMPTZ,
    last_succeeded_at   TIMESTAMPTZ,
    last_failed_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- BOT RUNTIME CONFIGURATION
-- ============================================================

CREATE TABLE bot_guild_config (
    guild_id         BIGINT PRIMARY KEY,
    is_active        BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_bot_guild_config_single_active
    ON bot_guild_config (is_active)
    WHERE is_active = true;

CREATE TABLE bot_channel_binding (
    guild_id         BIGINT NOT NULL REFERENCES bot_guild_config(guild_id) ON DELETE CASCADE,
    binding_key      TEXT NOT NULL,
    channel_id       BIGINT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, binding_key)
);

CREATE TABLE bot_role_binding (
    guild_id         BIGINT NOT NULL REFERENCES bot_guild_config(guild_id) ON DELETE CASCADE,
    binding_key      TEXT NOT NULL,
    role_id          BIGINT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, binding_key)
);

-- ============================================================
-- BOT QUEUES
-- ============================================================

CREATE TABLE bot_queue (
    queue_id         TEXT PRIMARY KEY,
    guild_id         BIGINT NOT NULL,
    label            TEXT NOT NULL,
    is_paused        BOOLEAN NOT NULL DEFAULT false,
    paused_reason    TEXT NOT NULL DEFAULT '',
    active_entry_id  UUID,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bot_queue_entry (
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

CREATE UNIQUE INDEX idx_bot_queue_one_active_entry
    ON bot_queue_entry (queue_id, state)
    WHERE state = 'active';

CREATE UNIQUE INDEX idx_bot_queue_user_current_entry
    ON bot_queue_entry (queue_id, discord_user_id);

CREATE INDEX idx_bot_queue_entry_order
    ON bot_queue_entry (queue_id, position, joined_at);

CREATE TABLE bot_queue_event (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id         TEXT NOT NULL REFERENCES bot_queue(queue_id) ON DELETE CASCADE,
    entry_id         UUID,
    event_type       TEXT NOT NULL,
    actor_user_id    TEXT,
    payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_bot_queue_event_queue_created_at
    ON bot_queue_event (queue_id, created_at DESC, id DESC);

-- ============================================================
-- BOT MILEAGE
-- ============================================================

CREATE TABLE bot_mileage_tier (
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

CREATE UNIQUE INDEX idx_bot_mileage_tier_guild_name
    ON bot_mileage_tier (guild_id, name);

CREATE INDEX idx_bot_mileage_tier_threshold
    ON bot_mileage_tier (guild_id, points_required DESC, sort_order ASC);

CREATE TABLE bot_mileage_total (
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

CREATE INDEX idx_bot_mileage_total_points
    ON bot_mileage_total (guild_id, total_points DESC, last_event_at DESC);

CREATE TABLE bot_mileage_event (
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

CREATE UNIQUE INDEX idx_bot_mileage_event_reversal_once
    ON bot_mileage_event (reversed_event_id)
    WHERE reversed_event_id IS NOT NULL;

CREATE INDEX idx_bot_mileage_event_user_created_at
    ON bot_mileage_event (guild_id, discord_user_id, created_at DESC, id DESC);

-- ============================================================
-- BOT AUDIT LOG
-- ============================================================

CREATE TABLE bot_audit_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id    TEXT,
    actor_session_id TEXT,
    action_key       TEXT NOT NULL,
    target_type      TEXT NOT NULL,
    target_key       TEXT NOT NULL,
    request_id       TEXT,
    before_state     JSONB,
    after_state      JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_bot_audit_log_created_at
    ON bot_audit_log (created_at DESC);

CREATE INDEX idx_bot_audit_log_target
    ON bot_audit_log (target_type, target_key, created_at DESC);

-- ============================================================
-- UPDATED_AT TRIGGER HELPER
-- ============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER movie_updated_at
    BEFORE UPDATE ON movie
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER page_updated_at
    BEFORE UPDATE ON page
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_operator_updated_at
    BEFORE UPDATE ON bot_operator
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_syndication_source_updated_at
    BEFORE UPDATE ON bot_syndication_source
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_syndication_checkpoint_updated_at
    BEFORE UPDATE ON bot_syndication_checkpoint
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_guild_config_updated_at
    BEFORE UPDATE ON bot_guild_config
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_channel_binding_updated_at
    BEFORE UPDATE ON bot_channel_binding
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_role_binding_updated_at
    BEFORE UPDATE ON bot_role_binding
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_queue_updated_at
    BEFORE UPDATE ON bot_queue
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_queue_entry_updated_at
    BEFORE UPDATE ON bot_queue_entry
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_mileage_tier_updated_at
    BEFORE UPDATE ON bot_mileage_tier
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER bot_mileage_total_updated_at
    BEFORE UPDATE ON bot_mileage_total
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
