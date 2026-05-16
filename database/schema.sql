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

-- connect / campaign channels
CREATE TABLE connect_channel (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    status      TEXT,               -- e.g. 'Primary', 'Support'
    description TEXT,
    sort_order  INT NOT NULL DEFAULT 0
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
