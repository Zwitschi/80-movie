# Open Mic Odyssey Architecture

## 1. Overview

Open Mic Odyssey currently ships as three Flask-based service surfaces around one shared PostgreSQL database: public website, control room, and bot API. Public site lives at `openmicodyssey.com`.

Current repository contains a standalone control room for editorial CMS routes under `/admin` plus operator routes under `/admin/bot`, with Discord OAuth operator login, operator/session management, health/config/command views, and syndication control APIs. Repository also contains a scaffolded bot worker runtime focused on configuration, startup lifecycle, and YouTube-first syndication polling. It still does **not** contain a feature-complete Discord gateway automation worker or a separate operator dashboard SPA.

### Current Product Goals

- Publish public-facing film site with trailer, story, credits, media, support, and connect pages.
- Give project team lightweight editorial CMS for updating film content without direct template edits.
- Generate search-friendly metadata through schema.org JSON-LD, sitemap, and robots outputs.
- Support both live Flask rendering and static site export for deployment flexibility.

### Planned Expansion Goals

- Add Discord bot for community automation, event queueing, mileage/XP, and content syndication.
- Add broader control-room surface for cross-system operations beyond website editorial content.
- Reuse shared production data safely across website and future community tooling.

### Related ADRs

- [ADR-001: Embedded-First Control Room](adr/ADR-001-embedded-first-control-room.md)
- [ADR-002: Shared Data Ownership And Integration Strategy](adr/ADR-002-shared-data-ownership-and-integration.md)

### Stakeholders

| Role                      | Expectation                                              |
| ------------------------- | -------------------------------------------------------- |
| Site owner                | Stable public film website and manageable deploy flow    |
| Editors/admins            | Simple authenticated forms for updating site content     |
| Audience                  | Fast public pages, clear calls to watch/support/connect  |
| Future community ops team | Path to add Discord automation without replacing website |

## 2. Scope

### Current In Scope

- Flask website runtime in `website/`
- Public pages, compatibility redirects, sitemap, robots, and hidden map route
- Standalone control room runtime in `control_room/`
- Editorial CMS routes under `/admin` on the control room service
- Operator routes, templates, and ops APIs under `/admin/bot` on the control room service
- Discord OAuth operator login for the control room
- PostgreSQL-backed content read/write layer
- JSON-LD schema generation from structured content
- Static export generation to `website/dist`
- Coolify/Nixpacks website deployment configuration
- Bot scaffold runtime in `bot/omo_bot/` for config parsing, startup lifecycle, operator-facing health/config inspection, and syndication polling seams
- Bot-owned operator and syndication persistence seams backed by PostgreSQL migrations

### Current Out Of Scope

- Feature-complete Discord gateway automation worker
- Queue, mileage / XP, onboarding, and moderation domains
- Separate React/Vite dashboard application
- Native mobile applications

### Known Documentation / Code Gap

Documentation and config mention `DATA_SOURCE=JSON` fallback, but current `website/movie_site/content_store.py` factory always returns DB-backed reader/writer. Architecture must treat DB-backed content as current implemented path.

## 3. Context

### Current System Context

Public visitors interact with a public Flask website deployed at openmicodyssey.com. Admin editors and bot operators interact with a separate Flask control room deployed at admin.openmicodyssey.com. Website, control room, bot API, and bot worker share one PostgreSQL database. The bot scaffold runtime runs as a separate process for config validation and syndication polling seams.

### Future-State Context

Three independent services share one PostgreSQL database:

- **Website** (openmicodyssey.com) serves public pages on port 8880.
- **Control Room** (admin.openmicodyssey.com) provides operator login, health/config views, and syndication control on port 8480.
- **Bot API** (api.openmicodyssey.com) exposes health, syndication, and bot management endpoints on port 8787.

All traffic routes through Nginx Proxy Manager on the Coolify server. The Discord bot worker connects to Discord's gateway API and reads/writes bot-owned tables in the shared database.

## 4. Technology Baseline

| Area             | Current Choice                                       | Notes                                       |
| ---------------- | ---------------------------------------------------- | ------------------------------------------- |
| Web framework    | Flask                                                | App factory plus blueprints                 |
| Templates        | Jinja2                                               | Shared layout and page templates            |
| Auth             | Flask-Login + username/password hash + Discord OAuth | Control room owns editorial + operator auth |
| Persistence      | PostgreSQL via `psycopg2`                            | Content tables back site/CMS                |
| Content assembly | Python dict aggregation                              | `movie_data.py` composes page payload       |
| SEO/schema       | schema.org JSON-LD                                   | Built in Python, rendered into templates    |
| Static export    | Python generator + BeautifulSoup + jsonschema        | Renders routes into `dist`                  |
| Deployment       | Coolify + Nixpacks + Gunicorn                        | Base directory `website`, port `8000`       |

### Configuration Surface

Current website config is driven by environment variables in `website/movie_site/config.py`:

- `SITE_URL`
- `DATABASE_URL`
- `DATA_SOURCE`
- `CURRENT_YEAR`
- `MAPBOX_ACCESS_TOKEN`
- `SECRET_KEY`

Current control-room config is driven by shared config helpers plus control-room app wiring:

- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`
- `OMO_DISCORD_CLIENT_ID` / `DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET` / `DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI` / `DISCORD_REDIRECT_URI`

## 5. Building Block View

### Level 1

```txt
┌────────────────────────────────────────────────────────────┐
│                    Open Mic Odyssey website                │
├────────────────────────────────────────────────────────────┤
│ Entrypoint                                                 │
│  └─ website/app.py                                         │
│                                                            │
│ App composition                                             │
│  └─ movie_site/__init__.py -> create_app()                 │
│                                                            │
│ Public web surface                                          │
│  └─ movie_site/views.py                                    │
│                                                            │
│ Admin CMS surface                                           │
│  ├─ movie_site/admin.py                                    │
│  ├─ movie_site/admin_content.py                            │
│  └─ movie_site/auth.py                                     │
│                                                            │
│ Content + SEO                                               │
│  ├─ movie_site/movie_data.py                               │
│  ├─ movie_site/content_store.py                            │
│  ├─ movie_site/content_store_db.py                         │
│  ├─ movie_site/schema.py                                   │
│  └─ movie_site/schema_parts/                               │
│                                                            │
│ Export + assets                                             │
│  ├─ generate_static_site.py                                │
│  ├─ templates/                                             │
│  └─ static/                                                │
└───────────────────────────────┬────────────────────────────┘
                                │
                                ▼
                     ┌────────────────────────┐
                     │ PostgreSQL + file env  │
                     └────────────────────────┘
```

### Current Building Blocks

| Building Block                                   | Responsibility                                                                        |
| ------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `website/app.py`                                 | Thin WSGI entrypoint exposing `app`                                                   |
| `website/movie_site/__init__.py`                 | Public website app factory, config loading, public blueprint registration             |
| `website/movie_site/views.py`                    | Public routes, page context, meta tags, sitemap, robots, hidden map page              |
| `website/movie_site/config.py`                   | Environment-driven defaults and secrets/config                                        |
| `website/movie_site/content_store.py`            | Content store factory abstraction                                                     |
| `website/movie_site/content_store_db.py`         | PostgreSQL-backed content read/write implementation                                   |
| `website/movie_site/db.py`                       | Connection-pool helper functions using `psycopg2`                                     |
| `website/movie_site/movie_data.py`               | Aggregates content records into page-ready data model                                 |
| `website/movie_site/schema.py` + `schema_parts/` | Builds JSON-LD graph for SEO/schema.org output                                        |
| `control_room/app.py`                            | Control-room app factory, auth wiring, blueprint registration                         |
| `control_room/admin.py`                          | Editorial CMS routes, login gate, dashboard entry, route delegation                   |
| `control_room/admin_content.py`                  | CRUD handlers for film, media, content, events, FAQ, people, connect, reviews, assets |
| `control_room/auth.py`                           | Flask-Login manager and admin user loader for editorial CMS                           |
| `control_room/admin_bot.py`                      | Operator routes, Discord OAuth flow, health/config/queue/mileage/syndication views    |
| `website/generate_static_site.py`                | Renders public routes into static HTML and validates output                           |

### Implemented Route Surface

Public routes in current code:

- `/`
- `/film`
- `/watch`
- `/connect`
- `/support`
- `/media`
- `/gallery`
- `/patreon`
- `/credits`
- `/map`
- `/robots.txt`
- `/sitemap.xml`

### Public Page Responsibilities

| Route          | Purpose                                                                    |
| -------------- | -------------------------------------------------------------------------- |
| `/`            | Landing page and main entry into trailer/support journey                   |
| `/film`        | Film-specific detail page including credits and deeper project information |
| `/media`       | Stills, poster, gallery, and other media presentation                      |
| `/connect`     | Public hub for official links, channels, and lightweight support actions   |
| `/patreon`     | Membership / supporter conversion page                                     |
| `/watch`       | Compatibility redirect into trailer section                                |
| `/credits`     | Compatibility redirect into credits section on film page                   |
| `/support`     | Compatibility redirect into connect/support flow                           |
| `/gallery`     | Compatibility redirect into media page                                     |
| `/map`         | Hidden easter egg route for road-trip route visualization                  |
| `/robots.txt`  | Search crawler policy                                                      |
| `/sitemap.xml` | Search index of public pages plus discovered static assets                 |

Admin routes in current code:

- `/admin`
- `/admin/login`
- `/admin/logout`
- `/admin/film`
- `/admin/media`
- `/admin/content`
- `/admin/events`
- `/admin/faq`
- `/admin/people`
- `/admin/connect`
- `/admin/connect/social`
- `/admin/connect/supporters`
- `/admin/connect/patreon`
- `/admin/media-assets`
- `/admin/reviews`
- `/admin/submissions`

### Admin CMS Coverage

Current admin surface supports editing or reviewing these content domains:

- Core film metadata and release-status fields
- Media gallery items and categories
- Page content and metadata blocks
- Screening events and offers
- FAQ entries
- People, contributors, and organizations
- Connect page sections, supporter links, Patreon messaging, and social links
- Media assets and review content

Admin dashboard currently uses one authenticated Flask surface rather than separate editorial API and SPA.

### Content Source Status

Logical site content is assembled from file-like payload names such as `movies.json`, `events.json`, `people.json`, `content.json`, `connect.json`, and `media_assets.json`, but current runtime implementation resolves those through PostgreSQL-backed reader/writer classes.

Documented intent:

- DB-backed content is default mode.
- JSON-backed content is described as optional mode via `DATA_SOURCE=JSON`.

Current code reality:

- `content_store.py` always returns DB implementation.
- Architecture should therefore treat DB-backed content management as current production behavior and JSON mode as unimplemented contract.

## 6. Runtime View

### Scenario: Public Page Render (Website)

1. Request reaches Flask website on port 8880.
2. `main_blueprint` route selects page template.
3. `build_page_context()` asks `movie_data.py` for aggregated content.
4. Content store reads structured data from PostgreSQL-backed layer.
5. View computes SEO metadata and JSON-LD payloads.
6. Jinja template renders final HTML with shared layout and schema script blocks.

### Scenario: Schema Generation (Website)

1. `movie_data.py` combines core movie data, people, organizations, reviews, offers, social links, connect content, FAQ, and media assets into unified payload.
2. `schema.py` asks `schema_parts/graph.py` for schema.org graph structure.
3. Schema helpers render node-level data for `Movie`, `Person`, `Organization`, `VideoObject`, `ScreeningEvent`, `Review`, `AggregateRating`, `Offer`, and `FAQPage`.
4. Final JSON-LD is serialized and injected into shared base template.

### Scenario: Admin Login (Control Room)

1. Editor requests `/admin` or child route on control room service.
2. `before_request` guard redirects unauthenticated user to `/admin/login`.
3. Login form checks submitted username against `ADMIN_USERNAME`.
4. Password is verified against `ADMIN_PASSWORD_HASH` via Werkzeug.
5. Flask-Login stores session and redirects back to requested admin route.

### Scenario: Admin Content Edit (Control Room)

1. Authenticated editor submits form to control-room admin route.
2. `control_room/admin.py` delegates to handler in `control_room/admin_content.py`.
3. Handler normalizes form data and builds logical content payload.
4. Content writer persists updates to PostgreSQL-backed content tables.
5. User is redirected back to editor with success or rendered with validation/save error.

### Scenario: Sitemap / Robots Generation (Website)

1. Request hits `/robots.txt` or `/sitemap.xml`.
2. `views.py` returns app-generated metadata response.
3. Sitemap enumerates public routes plus static asset paths discovered from structured movie data.

### Scenario: Static Export (Website)

1. Static generator builds Flask app in-process.
2. Test client requests explicit public routes.
3. HTML is rewritten for flat-file output.
4. Static assets are copied into export tree.
5. Output is validated for HTML structure and JSON-LD envelope shape.
6. Files are written into `website/dist`.

### Scenario: Hidden Map Page (Website)

1. Request hits `/map` directly; route is intentionally excluded from normal sitemap page list.
2. View renders dedicated map template with standard movie page context.
3. Client-side map code reads route data from `website/static/data/map_data.json`.
4. Map rendering depends on configured `MAPBOX_ACCESS_TOKEN`.

### Scenario: Operator Login (Control Room)

1. Operator requests `/admin/bot/login` on control room service (port 8480).
2. Control room renders Discord OAuth start button.
3. Operator authorizes via Discord; callback returns to `/oauth/discord/callback`.
4. Control room validates OAuth state, fetches Discord identity, resolves local operator record.
5. Operator session created with scoped permissions (`ops.read`, `queue.write`, etc.).
6. Operator redirected to control room overview.

### Scenario: Bot Health Check (Control Room / Bot API)

1. Operator opens Health screen on control room (port 8480).
2. Control room calls `GET /admin/bot/api/health` on bot API service (port 8787).
3. Bot API returns runtime state, DB reachability, job freshness, config presence.
4. Control room renders health dashboard with status indicators.

### Scenario: Syndication Polling (Bot Worker)

1. Bot worker starts, loads config from env and DB.
2. Syndication polling job runs on configured interval (default 300s).
3. Job queries YouTube adapter for new content since last checkpoint.
4. New items are normalized and posted to configured Discord channels.
5. Checkpoint updated in `bot_syndication_checkpoint` table.
6. Control room can inspect source status and trigger retries via bot API.

### Scenario: Queue Management (Control Room + Bot API)

1. Moderator opens Queue screen on control room (port 8480).
2. Control room fetches queue list from bot API (port 8787).
3. Moderator advances queue via `POST /admin/bot/api/queues/{queue_id}/advance`.
4. Bot API validates scope (`queue.write`), updates queue state, emits audit entry.
5. Control room refreshes queue detail view with updated state.

## 7. Deployment View

### Infrastructure

All services deploy on a single Coolify server at `coolify.allucanget.biz` (internal IP `192.168.88.18`). Nginx Proxy Manager handles TLS termination and domain routing. PostgreSQL runs on a separate internal host at `192.168.88.35`.

### Service Routing

| Domain                                         | Internal Target             | Port | Service      |
| ---------------------------------------------- | --------------------------- | ---- | ------------ |
| `openmicodyssey.com`, `www.openmicodyssey.com` | `http://192.168.88.18:8880` | 8880 | Website      |
| `admin.openmicodyssey.com`                     | `http://192.168.88.18:8480` | 8480 | Control Room |
| `api.openmicodyssey.com`                       | `http://192.168.88.18:8787` | 8787 | Bot API      |

### Database

PostgreSQL is always available at `192.168.88.35`. All three services connect to the same database instance with separate table ownership:

- Website owns editorial tables (`movie`, `gallery_item`, `faq_item`, etc.)
- Bot owns operational tables (`bot_guild_config`, `bot_queue`, `bot_mileage_event`, `bot_syndication_source`, etc.)
- Shared integration tables exist for cross-surface read models

### Coolify Deployment

Each service deploys as an independent Coolify Application resource:

| Service      | Base Directory  | Start Command                                      | Port | Health Check                |
| ------------ | --------------- | -------------------------------------------------- | ---- | --------------------------- |
| Website      | `website/`      | `gunicorn app:app --bind 0.0.0.0:8880 --workers 2` | 8880 | `GET /robots.txt`           |
| Control Room | `control_room/` | `gunicorn app:app --bind 0.0.0.0:8480 --workers 2` | 8480 | `GET /admin/bot/api/health` |
| Bot API      | `bot_api/`      | `gunicorn app:app --bind 0.0.0.0:8787 --workers 2` | 8787 | `GET /health`               |
| Bot Worker   | `/` (repo root) | `python -m bot.omo_bot`                            | none | process alive               |

### Nginx Proxy Manager

Nginx Proxy Manager is pre-configured with proxy hosts for all three domains. Each proxy host:

- Routes to the corresponding internal IP and port
- Handles TLS via Let's Encrypt (managed by NPM)
- Forwards `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` headers
- No additional Nginx configuration needed in this project

### Static Export Support

Repository also supports generating static HTML output from same public routes. That export path is additional deployment option and content validation tool, not separate product.

### Runtime Configuration Notes

- `SITE_URL` controls canonical URL generation, metadata URLs, and sitemap roots.
- `CURRENT_YEAR` feeds shared page/footer context.
- `MAPBOX_ACCESS_TOKEN` is only required for hidden map experience.
- Website `SECRET_KEY` governs public-site session state.
- Control room `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH` govern editorial CMS session auth.
- `DATABASE_URL` controls PostgreSQL connection pool target (points to `192.168.88.35`).
- `DATA_SOURCE` is present in config surface, but does not currently switch runtime away from DB-backed content store.

### Required Environment Variables

- `SECRET_KEY`
- `SITE_URL`
- `DATABASE_URL`

### Optional Environment Variables

- `MAPBOX_ACCESS_TOKEN`
- `CURRENT_YEAR`
- `DATA_SOURCE` (documented, but currently not effective as runtime switch)

### Control Room Required Environment Variables

- `SECRET_KEY`
- `DATABASE_URL`
- `ADMIN_PASSWORD_HASH`

### Control Room Optional Environment Variables

- `ADMIN_USERNAME`
- `OMO_DISCORD_CLIENT_ID` / `DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET` / `DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI` / `DISCORD_REDIRECT_URI`

### Testing Notes

Tests should not rely on a live database connection. Use in-memory repositories or mocked DB layers for test execution. The PostgreSQL instance at `192.168.88.35` is for production/runtime use only.

## 8. Security And Operations

### Current Security Model

- Public site is anonymous-read.
- Admin CMS uses Flask session auth with configured username and password hash.
- Embedded control-room operator auth uses Discord OAuth plus locally managed operator scopes and session idle timeout rules.
- Secrets are environment-based.
- Hidden `/map` page still depends on public Mapbox token for client-side rendering.

### Current Operational Characteristics

- App is small modular Flask codebase with public, editorial admin, and embedded control-room blueprints.
- Structured content is assembled dynamically for page render and sitemap generation.
- Static export path gives additional confidence in route renderability and schema validity.
- Bot worker runtime can start independently for config validation, lifecycle smoke checks, and syndication polling seam wiring, but it is not yet a feature-complete Discord automation service.

## 9. Testing And Quality

### Current Automated Coverage

Existing pytest suite covers at least:

- Public route success responses
- Static asset serving
- `robots.txt`
- `sitemap.xml`
- Presence of JSON-LD in rendered pages
- Static export route rewriting and validation helpers

### Known Validation Gap

Tracked website test files currently pass under the project virtual environment. Recent fixes aligned tests with the DB-backed content store and made static-export cleanup work on Windows.

### Quality Priorities For Current Website

| Priority | Goal                   | Current Meaning                                                 |
| -------- | ---------------------- | --------------------------------------------------------------- |
| 1        | Publishing reliability | Public pages and admin edits should render consistently         |
| 2        | Content correctness    | CMS writes should preserve structured data and schema outputs   |
| 3        | Search visibility      | Metadata, JSON-LD, sitemap, and robots output should stay valid |
| 4        | Deployment simplicity  | Coolify deploy and static export should remain straightforward  |

## 10. Risks And Technical Debt

### Current Risks

| Priority | Risk                                                | Impact                                       | Mitigation Direction                                            |
| -------- | --------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| High     | Architecture docs drift from implemented website    | Wrong planning assumptions                   | Keep doc grounded in current code and label future work clearly |
| High     | Documented JSON fallback not actually wired         | Misleading runtime expectations              | Either implement switch or update docs/config contract          |
| Medium   | Admin auth is single shared credential model        | Limited operator separation and auditability | Revisit when multi-user admin or ops dashboard appears          |
| Medium   | Map route depends on external Mapbox token          | Broken map experience if token missing       | Validate env in deploy and static export contexts               |
| Medium   | DB helper lifecycle registration appears incomplete | Connection management may drift over time    | Review whether `db.init_app()` should be wired in app factory   |

### Current Technical Debt

- Architecture doc had been rewritten around unimplemented bot system instead of existing website.
- README and config describe JSON-vs-DB content source choice, but code path is DB-only today.
- Some route inventory and admin capabilities are documented incompletely across files.
- Remaining test debt is mostly coverage depth around admin CRUD flows and DB lifecycle behavior, not baseline test execution.

## 11. Planned Expansion

### Relationship Between Website, Bot, And Control Room

| Surface                | Primary Responsibility                            | Should Own                                                                                           | Should Not Own                                                         |
| ---------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Existing Flask website | Public film presence and editorial publishing     | Public pages, CMS workflows, schema/SEO, static export, canonical site content                       | Discord-native automation, queue state, community moderation workflows |
| Planned Discord bot    | Community automation and Discord-side interaction | Guild config, queue state, mileage/XP events, syndication checkpoints, Discord role/event actions    | Public website rendering, Jinja templates, editorial page CMS          |
| Planned control room   | Cross-surface operations and monitoring           | Operator views, health/metrics, moderation tooling, manual sync and admin workflows spanning systems | Direct Discord gateway logic, public-site page rendering               |

### Shared Data Strategy

Preferred direction:

- Keep website as source of truth for public-facing editorial content.
- Let future bot own Discord-native operational state in dedicated tables.
- Share only intentional cross-surface data through explicit PostgreSQL schema contracts or shared domain modules.

#### PostgreSQL Ownership Rules

Start with a single shared PostgreSQL instance but strict write ownership.

| Ownership bucket                       | Write owner                                                       | Readers                                                                  | Current / planned tables                                                                                                                                                                                                                                                                                                                             | Notes                                                                                                            |
| -------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Website-owned editorial data           | Website app and admin CMS only                                    | Website, bot, future control room                                        | `movie`, `movie_release_status`, `trailer`, `review`, `aggregate_rating`, `offer`, `movie_offer`, `screening_event`, `screening_offer`, `faq_item`, `gallery_item`, `social_link`, `connect_campaign`, `connect_channel`, `connect_page`, `patreon_benefit`, `patreon_tier`, `page`, `person`, `organization`, `organization_member`, `movie_credit` | Bot may read these tables for announcements, reminders, and sync decisions, but should not update them directly. |
| Bot-owned operational data             | Bot service only                                                  | Bot, future control room, website read models if explicitly needed later | `bot_guild_config`, `bot_channel_binding`, `bot_role_binding`, `bot_queue`, `bot_queue_entry`, `bot_queue_event`, `bot_mileage_event`, `bot_mileage_total`, `bot_mileage_tier`, `bot_syndication_source`, `bot_syndication_checkpoint`, `bot_audit_log`                                                                                              | Prefix bot-owned tables to make ownership visible in migrations, queries, and backups.                           |
| Shared read models / integration state | Bot writes first; control room may later own projection refreshes | Website, bot, control room                                               | `bot_event_sync_state`, `bot_announcement_projection`                                                                                                                                                                                                                                                                                                | Keep these append-only or rebuildable. Do not treat them as the source of truth for editorial content.           |

Rules:

- Each table has exactly one write owner.
- Cross-surface reads are allowed; cross-surface writes are not.
- If one surface needs to request a mutation in another surface's data, do it through a service/API boundary or an owner-controlled integration table, not an ad hoc SQL write.
- Shared migrations must preserve deploy independence: website deploys cannot require bot code rollout in the same step, and bot deploys cannot rewrite website-owned data shapes without a compatibility window.
- Do not let public page rendering depend on bot-owned tables for correctness.

Shared data candidates:

- Production metadata reused in public site and community announcements
- Screening/event records where website listings and community reminders should stay aligned
- External-link or campaign metadata reused across public pages and community surfaces

#### Minimal Shared DTO / Domain Contract

Keep the first shared contract intentionally small and read-only.

| DTO                     | Source of truth               | Required fields                                                                                               | Consumers                                                |
| ----------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `ProductionMetadata`    | Website editorial tables      | `movie_id`, `title`, `tagline`, `release_status`, `poster_image`, `trailer_url`, `site_url`                   | Website templates, bot announcement/syndication services |
| `ScreeningEventSummary` | Website event tables          | `event_id`, `name`, `start_at`, `end_at`, `status`, `venue_name`, `venue_locality`, `ticket_url`, `site_path` | Website pages, bot reminders, future control room views  |
| `CampaignLinkSummary`   | Website connect/social tables | `label`, `url`, `status`, `category`, `sort_order`                                                            | Website connect pages, bot promo/admin commands          |

Contract rules:

- Shared DTOs should be assembled from website-owned read models, not by leaking Flask view helpers into the bot.
- DTOs should avoid presentation-only fields such as rendered HTML snippets or template fragments.
- If a field is expensive or unstable, keep it out of the initial contract until two surfaces actually need it.
- Version DTO changes like database contract changes: additive first, breaking only after both consumers are updated.

Avoid coupling patterns:

- Bot reading Jinja templates or website view helpers directly
- Dashboard bypassing service boundaries to mutate Discord state ad hoc
- Website templates depending on bot runtime tables for page rendering

### Integration Points

Planned integration boundaries:

- Website -> bot: optional content publish hooks, event metadata exposure, shared DB read model, or internal admin API calls
- Bot -> website: optional status sync, surfaced event/community data, or controlled writes to shared integration tables
- Control room -> website and bot: authenticated operator API calls or DB-backed read models, never direct Discord gateway ownership

Recommended starting model:

- Shared PostgreSQL instance
- Separate table ownership by subsystem
- Thin shared schema/domain package only for stable shared concepts
- Internal APIs added only when direct shared-table access becomes unsafe or too coupled

Confirmed near-term product decision:

- Start shared integrations with direct DB-backed read contracts and owner-controlled integration tables where needed.
- Introduce internal APIs for cross-surface writes, unstable domains, or service-owned authorization checks.

### Auth Model

Current and planned auth boundaries should stay separate at first:

- Website admin auth remains Flask-Login session auth for editorial CMS.
- Bot service auth should use service-level secrets/config, not website session cookies.
- Future control room should use its own operator auth layer and call internal website/bot APIs with explicit credentials.
- Discord OAuth is already the operator login path for the embedded `/admin/bot` control room and is not a prerequisite for the editorial CMS.

Confirmed near-term product decision:

- Keep Discord OAuth as the control-room operator authentication path through the embedded-first phase and the first extracted control-room phase.
- Keep authorization local through explicit operator scopes rather than Discord guild membership alone.
- Do not converge control-room auth with the editorial CMS credential model.
- Keep onboarding and role-automation operator workflows on the same Discord-OAuth-backed operator boundary instead of introducing a second auth system first.

### Deployment Relationship

- Website remains independently deployable on Coolify as web app.
- Current bot scaffold can already run as a separate process, and the future bot should mature into a long-lived worker/service process.
- Future control room may be separate SPA or separate Flask/API surface, but should deploy independently from public website shell when possible.
- Shared database migrations must preserve subsystem ownership to avoid one surface breaking another during deploy.

Post-stability revisit outcome:

- Keep the control room embedded through the next onboarding and role-automation phase.
- Do not extract a separate control-room deployment until onboarding and operator workflows create clear pressure for independent release cadence, richer realtime UX, or a different auth model.
- Preserve `/admin/bot/api/*` as the extraction seam so later separation is incremental instead of a rewrite.

### Current Bot Status And Planned Discord Bot

Implemented today:

- bot runtime config parsing and env loading
- runtime startup and shutdown lifecycle scaffold
- YouTube-first syndication adapter, repository, and polling job seams
- embedded control-room operator auth, health/config/commands pages, and syndication actions
- bot operator and syndication persistence migrations

Still planned:

Intended next domains still under consideration:

- Community onboarding and role assignment
- Event queue management
- Mileage / XP tracking
- Content syndication from external channels
- Admin and moderation commands

### Planned Bot Feature Roadmap

#### MVP Features

| Domain         | Planned Capabilities                                                                     | Notes                                                                        |
| -------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Onboarding     | Welcome flow, reaction-role or command-based role assignment, starter channel guidance   | Keep role mapping config-driven                                              |
| Event queue    | Join/leave/advance queue commands, queue visibility, moderator controls                  | Start with text-command + slash-command support if needed                    |
| Mileage / XP   | Point awards for configured events, aggregate totals, milestone tiers, admin adjustments | Separate raw event log from user totals                                      |
| Syndication    | Post new content updates into Discord from selected sources                              | Start with polling/checkpoint model; MVP automation begins with YouTube only |
| Admin controls | Health/status commands, config inspection, manual sync/retry commands                    | Reserve destructive commands for privileged roles                            |

#### Confirmed MVP Syndication Scope

- The first automated external syndication source is YouTube.
- Instagram and TikTok remain public-facing channels and planned future adapters, but they are explicitly out of MVP automation scope.
- Website-owned editorial content can still feed Discord announcements separately through website-owned read models or integration tables; that does not change the external-source MVP decision.

Reason:

- YouTube is already a first-class public channel in the project content.
- A polling and checkpoint model fits YouTube more cleanly than it fits Instagram or TikTok.
- Deferring Instagram and TikTok avoids brittle MVP automation assumptions around upstream API stability and access.

#### Phase 2 Features

- Scheduled reminders for screenings or tour-stop events
- Better moderation tooling around queue management and role cleanup
- Cross-posting of selected website content or campaign updates into Discord
- Lightweight analytics surfaced to operators
- Audit log for sensitive admin actions

#### Later / Nice-To-Have Features

- Multi-guild support with isolated configuration
- Discord OAuth bridge for operator workflows or member-facing sync
- Automated reconciliation between website event data and Discord reminders
- Expanded adapter set beyond initial content sources
- Advanced role progression, seasonal campaigns, or gamification layers

### Planned Bot Domains

#### Onboarding And Roles

- Assign and revoke configured Discord roles
- Gate flows by guild-specific configuration
- Support future welcome messaging and newcomer guidance

Current revisit decision:

- Build onboarding and role automation as bot-owned domain logic, not as editorial-CMS behavior.
- Keep the embedded control room limited to configuration, inspection, retries, and privileged overrides for onboarding flows.
- Treat onboarding configuration as repository/service state with explicit audit coverage, following the same pattern now used for config, queue, and mileage.

#### Queue And Event Operations

- Maintain FIFO queue for performances, screenings, or open-mic participation
- Support moderator-only advance/remove/clear actions
- Publish queue state to channels or dashboard read models

#### Mileage And Progression

- Record granular engagement events
- Maintain aggregate per-user totals
- Map totals to milestone tiers or roles
- Support manual correction without losing event history

#### Content Syndication

- Poll selected external sources for new content
- Track last-seen checkpoint per source
- Post normalized announcements to configured channels
- Retry safely without duplicate spam

#### Admin / Moderation Commands

- Runtime health and config inspection
- Queue and mileage overrides for privileged operators
- Manual content re-sync or syndication retry hooks
- Safe diagnostics without exposing secrets

### Planned Persistence Needs

#### Bot-Owned Table Plan

Phase 1 should create bot-owned tables in this order:

| Phase                  | Tables                                                                 | Purpose                                                                            | Migration notes                                                                                                               |
| ---------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 1. Configuration       | `bot_guild_config`, `bot_channel_binding`, `bot_role_binding`          | Per-guild runtime config and channel/role mappings                                 | Create unique constraints on `(guild_id)` and `(guild_id, binding_key)` style pairs before any feature tables depend on them. |
| 2. Queue               | `bot_queue`, `bot_queue_entry`, `bot_queue_event`                      | Current queue state plus append-only history for moderator actions and transitions | Keep `bot_queue` small and current-state oriented; put immutable transitions in `bot_queue_event`.                            |
| 3. Mileage             | `bot_mileage_event`, `bot_mileage_total`, `bot_mileage_tier`           | Raw engagement ledger, rollup totals, and tier policy definitions                  | Treat `bot_mileage_event` as source of truth and rebuild `bot_mileage_total` if aggregation logic changes.                    |
| 4. Syndication         | `bot_syndication_source`, `bot_syndication_checkpoint`                 | Source configuration and last-processed cursor/checkpoint state                    | Use stable external source keys and idempotent uniqueness constraints to prevent duplicate announcements.                     |
| 5. Audit / integration | `bot_audit_log`, `bot_event_sync_state`, `bot_announcement_projection` | Sensitive operator audit trail and rebuildable sync/projection data                | Keep projections disposable; audit log is append-only.                                                                        |

Recommended migration rules:

- Put bot-owned DDL in separate migration files from website editorial DDL, even if they share the same database.
- Prefer additive migrations first: create tables, backfill, dual-read if needed, then enforce stricter constraints.
- Use append-only history tables for queue, mileage, and audit domains so operator actions remain traceable.
- Avoid foreign keys from website-owned tables into bot-owned tables. If a link is needed, point from bot-owned rows back to website identifiers.
- For shared event sync, store the website event UUID or natural key as a reference, but keep bot scheduling and delivery state in bot-owned tables.

### Planned Non-Functional Requirements

| Area          | Requirement                                                                        |
| ------------- | ---------------------------------------------------------------------------------- |
| Availability  | Bot should recover cleanly from restart and resume polling/checkpoint work         |
| Rate limiting | Discord and upstream APIs need explicit backoff and retry rules                    |
| Idempotency   | Repeated sync or poll runs must not duplicate posts or corrupt totals              |
| Auditability  | Admin actions and manual overrides should be traceable                             |
| Security      | Secrets remain environment-based; privileged commands require explicit role checks |
| Operability   | Health, logs, and manual recovery hooks should exist before broad rollout          |

### Current And Planned Bot Code Structure

Current repository shape already follows this boundary, with queue, mileage, onboarding, reminder, and richer adapter modules still to be added:

```txt
bot/
    omo_bot/
        __init__.py
        main.py
        config.py
        runtime/
            client.py
            startup.py
            shutdown.py
        commands/
            onboarding.py
            queue.py
            mileage.py
            admin.py
            health.py
        events/
            members.py
            reactions.py
            scheduled.py
        services/
            onboarding_service.py
            queue_service.py
            mileage_service.py
            syndication_service.py
            sync_service.py
        repositories/
            guild_config_repo.py
            queue_repo.py
            mileage_repo.py
            syndication_repo.py
            audit_repo.py
        adapters/
            discord_gateway.py
            youtube.py
            instagram.py
            tiktok.py
            website_sync.py
        models/
            queue.py
            mileage.py
            syndication.py
        jobs/
            polling.py
            reminders.py
tests/
    bot/
```

Alternative naming such as `src/omo_bot/` is also acceptable, but bot code should stay isolated from `website/` package boundaries.

### Module Boundary Guidance

| Layer               | Responsibility                                                  | Should Not Do                                    |
| ------------------- | --------------------------------------------------------------- | ------------------------------------------------ |
| `main.py` / runtime | Bootstrap process, load config, start Discord client, wire jobs | Hold business rules                              |
| `commands/`         | Parse command input and call services                           | Contain persistence logic                        |
| `events/`           | React to Discord events and dispatch service calls              | Contain SQL or external API details              |
| `services/`         | Core business logic and orchestration                           | Know Discord SDK details beyond small interfaces |
| `repositories/`     | Read/write bot-owned tables and shared read models              | Render Discord messages or route command flow    |
| `adapters/`         | Integrate external systems and APIs                             | Store cross-domain business policy               |
| `jobs/`             | Schedule polling, reminders, reconciliation work                | Duplicate service rules                          |
| `models/`           | Typed domain objects / DTOs                                     | Execute side effects                             |

### Shared-Code Boundary With Website

Keep these concerns website-only:

- Flask app factory and blueprints
- Jinja templates and page rendering helpers
- SEO/schema rendering and public-route response assembly
- Editorial CMS forms and handlers

Only extract shared code when it is both stable and needed by more than one surface. Candidate shared modules later:

- Shared DB schema constants or migration contracts
- Shared content/event DTOs for cross-surface reads
- Shared config parsing helpers for overlapping env vars

Avoid early extraction of generic utilities just to reduce duplication. Stable boundary more important than premature reuse.

### Planned Testing Strategy For Bot

| Test Level               | Scope                                             | Examples                                                          |
| ------------------------ | ------------------------------------------------- | ----------------------------------------------------------------- |
| Unit                     | Service logic in isolation                        | queue transitions, mileage calculations, role-tier evaluation     |
| Contract                 | Adapter behavior against mocked upstream payloads | syndication source normalization, Discord message formatting      |
| Repository / integration | DB persistence against test schema                | queue state writes, mileage event aggregation, checkpoint updates |
| Runtime smoke            | Bot startup and command registration              | config load, command table wiring, scheduled job registration     |

Recommended test order:

1. Service-level unit tests first.
2. Repository tests for bot-owned persistence.
3. Adapter contract tests for external inputs.
4. Minimal runtime smoke tests to ensure bootstrapping remains intact.

### Code Structure Principles

- Business rules live in services, not command handlers.
- Repositories own SQL and persistence mapping.
- Adapters normalize external systems into internal domain shapes.
- Jobs call services; they should not embed alternate business logic.
- Shared website/bot concerns should cross package boundary only through explicit contracts.

### Planned Control Room

Future control-room surface should likely separate operational tooling from website editorial CMS. Current Flask admin already serves editorial content management well, but bot operations will need different data, auth, and UI flows.

### Control Room Scope

Planned control room should focus on operator workflows that span systems rather than duplicate website page editing.

Primary responsibilities:

- Bot health and runtime status
- Queue visibility and moderator operations
- Mileage / XP inspection and admin adjustments
- Syndication status, checkpoints, and retry tools
- Cross-system sync visibility for website events or announcements
- Audit/log views for sensitive operator actions

Should remain outside control-room scope:

- Public page rendering
- Jinja/template editing concerns
- Direct Discord gateway ownership
- Replacement of current editorial CMS for basic website content work

### Dashboard Architecture Options

| Option                           | Description                                                                              | Pros                                                                                                         | Cons                                                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| A. Extend Flask admin            | Keep website CMS and future bot ops inside current Flask admin surface                   | Reuses existing deployment path, fastest path to usable operator tooling, easiest way to prototype UI flows  | Couples unrelated workflows, mixes editorial UI with ops UI, makes long-term separation harder |
| B. Separate control-room surface | Keep editorial CMS in Flask, create separate operator dashboard backed by bot/admin APIs | Cleaner boundaries, independent deploy cadence, auth can evolve separately, easier to model cross-system ops | Requires extra API and UI scaffolding                                                          |

Recommended direction: phased approach.

Phase 1 decision:

- Start inside the existing Flask app under `/admin/bot`.
- Keep operator routes, templates, and auth/session handling isolated from the editorial CMS.
- Use Discord OAuth for control-room operator login instead of reusing the single shared editorial credential.

Phase 2 direction:

- Re-evaluate extraction into a separate control-room surface once bot operations outgrow the embedded admin shell or require independent scaling/deploy cadence.

Reason:

- Embedded-first is the lowest-friction way to get operators a usable surface while bot domains are still being defined.
- Separate auth and route boundaries prevent the first version from becoming "just more CMS".
- Longer-term architectural pressure still points toward separation if live ops, richer permissions, or independent release cadence become important.

### Planned API Boundaries

Control room should talk to backend service boundaries, not directly to Discord APIs.

Preferred API split:

- Website CMS APIs remain optional and narrow, only for shared editorial or sync tasks.
- Bot admin/API surface owns queue controls, mileage adjustments, syndication controls, health endpoints, and ops read models.
- Control room consumes those APIs with explicit operator auth.

### Ops API Surface

For the embedded-first phase, keep operator-facing endpoints under the Flask-hosted control-room boundary, but treat them as ops APIs rather than page handlers. A practical initial namespace is `/admin/bot/api/*` even if the logical domain is still referred to as `/ops/*` in docs.

#### API Conventions

| Concern        | Initial rule                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Auth           | Require separate operator session established via Discord OAuth; do not reuse editorial CMS session.                            |
| Authorization  | Enforce explicit operator roles/scopes such as `ops.read`, `queue.write`, `mileage.write`, `syndication.write`.                 |
| Response shape | Return JSON with top-level `data`, optional `meta`, and structured `error` payloads.                                            |
| Auditability   | All write endpoints should emit audit entries with actor, action, target, request id, and before/after summary when applicable. |
| Idempotency    | Retry/reset/adjust actions should accept idempotency keys or use safe dedup semantics when repeated.                            |
| Time           | Use ISO 8601 UTC timestamps in payloads.                                                                                        |
| Pagination     | Use cursor or `limit` plus stable sort for event/history endpoints.                                                             |
| Separation     | Page routes render HTML; `/api` routes return machine-readable ops data only.                                                   |

Suggested error contract:

```json
{
  "error": {
    "code": "queue_conflict",
    "message": "Queue was modified by another operator.",
    "details": {
      "queue_id": "guild-123:open-mic"
    }
  }
}
```

#### Health Endpoints

| Endpoint                                                         | Purpose                                                | Returns                                                                                    | Notes                               |
| ---------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------ | ----------------------------------- |
| `GET /admin/bot/api/health`                                      | Overview health snapshot for control-room landing page | bot runtime status, bot API reachability, job freshness, config presence, degraded domains | Main operator heartbeat endpoint    |
| `GET /admin/bot/api/health/services`                             | Dependency-level detail                                | Discord connectivity state, DB reachability, scheduler state, background worker status     | Use for Health screen drill-down    |
| `GET /admin/bot/api/health/jobs`                                 | Background job execution status                        | last run, next run, last success, consecutive failures, stale flag per job                 | Covers polling, sync, reminder jobs |
| `POST /admin/bot/api/health/incidents/{incident_id}/acknowledge` | Mark an active incident acknowledged                   | updated incident state and actor metadata                                                  | Write action must be audited        |

Health payload should be optimized for operator triage, not low-level metrics dumping.

#### Queue Endpoints

| Endpoint                                                          | Purpose                                                | Returns                                                                           | Notes                                             |
| ----------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------- |
| `GET /admin/bot/api/queues`                                       | List queues by guild/event/channel with summary status | queue ids, labels, sizes, paused state, active entry, waiting count, last updated | Supports Overview and Queue index                 |
| `GET /admin/bot/api/queues/{queue_id}`                            | Queue detail                                           | queue metadata, ordered entries, moderator flags, last transition summary         | Primary queue detail view                         |
| `GET /admin/bot/api/queues/{queue_id}/events`                     | Queue history stream                                   | append-only queue transitions and moderator actions                               | Paginated; stable reverse-chronological ordering  |
| `POST /admin/bot/api/queues/{queue_id}/advance`                   | Advance active queue                                   | updated queue snapshot plus emitted transition summary                            | Require `queue.write`                             |
| `POST /admin/bot/api/queues/{queue_id}/entries/{entry_id}/remove` | Remove a queued entry                                  | updated queue snapshot and removal event                                          | Include reason in request body                    |
| `POST /admin/bot/api/queues/{queue_id}/entries/{entry_id}/move`   | Reorder an entry                                       | updated queue snapshot and move event                                             | Body should include target position               |
| `POST /admin/bot/api/queues/{queue_id}/pause`                     | Pause queue operations                                 | queue state                                                                       | Should support reason/comment                     |
| `POST /admin/bot/api/queues/{queue_id}/resume`                    | Resume queue operations                                | queue state                                                                       | Complement to pause                               |
| `POST /admin/bot/api/queues/{queue_id}/clear`                     | Clear queue intentionally                              | queue state and clear event summary                                               | High-risk action; confirmation and audit required |

Queue write endpoints should return both current-state data and a lightweight event summary so UI state and audit history stay aligned.

#### Mileage Endpoints

| Endpoint                                                | Purpose                                        | Returns                                                        | Notes                                                                  |
| ------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `GET /admin/bot/api/mileage/users`                      | Search/list mileage users                      | user summaries with totals, current tier, most recent activity | Filter by guild, tier, name, Discord id                                |
| `GET /admin/bot/api/mileage/users/{user_id}`            | Mileage user detail                            | totals, tier state, recent event ledger, pending flags         | Primary Mileage detail view                                            |
| `GET /admin/bot/api/mileage/users/{user_id}/events`     | Full mileage ledger                            | append-only mileage events and manual corrections              | Paginated event history                                                |
| `POST /admin/bot/api/mileage/users/{user_id}/adjust`    | Manual mileage adjustment                      | updated totals plus adjustment event                           | Request body should include delta, reason, and optional correlation id |
| `POST /admin/bot/api/mileage/events/{event_id}/reverse` | Reverse a prior event without deleting history | updated totals plus reversal event                             | Prefer reversal rows over destructive deletes                          |
| `GET /admin/bot/api/mileage/tiers`                      | Tier definitions and thresholds                | tier config list and counts by tier                            | Useful for config inspection and disputes                              |

Mileage domain should preserve ledger semantics: no endpoint should hard-delete history that affects totals.

#### Syndication Endpoints

| Endpoint                                                                                | Purpose                                  | Returns                                                                     | Notes                                      |
| --------------------------------------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------ |
| `GET /admin/bot/api/syndication/sources`                                                | List configured sources                  | source config summary, enabled state, last checkpoint, last success/failure | Supports Overview and Syndication index    |
| `GET /admin/bot/api/syndication/sources/{source_id}`                                    | Source detail                            | source config, current checkpoint, recent deliveries, dedup state           | Primary source detail view                 |
| `GET /admin/bot/api/syndication/sources/{source_id}/deliveries`                         | Delivery/retry history                   | successful posts, suppressed duplicates, recent failures                    | Paginated                                  |
| `POST /admin/bot/api/syndication/sources/{source_id}/retry`                             | Retry failed or pending syndication work | updated source status and retry job summary                                 | Require `syndication.write`                |
| `POST /admin/bot/api/syndication/sources/{source_id}/disable`                           | Disable a source                         | updated enabled state                                                       | Include reason/comment                     |
| `POST /admin/bot/api/syndication/sources/{source_id}/checkpoint/reset`                  | Reset checkpoint intentionally           | updated checkpoint state                                                    | High-risk action; audit required           |
| `POST /admin/bot/api/syndication/sources/{source_id}/deliveries/{delivery_id}/suppress` | Mark delivery suppressed or ignored      | updated delivery state                                                      | Use for operator-managed duplicate control |

Syndication endpoints should expose enough payload metadata for debugging, but should not leak tokens, raw credentials, or unsafe upstream secrets.

#### Suggested MVP Endpoint Set

If the first release needs a smaller scope, start with these:

- `GET /admin/bot/api/health`
- `GET /admin/bot/api/queues`
- `GET /admin/bot/api/queues/{queue_id}`
- `POST /admin/bot/api/queues/{queue_id}/advance`
- `GET /admin/bot/api/mileage/users/{user_id}`
- `POST /admin/bot/api/mileage/users/{user_id}/adjust`
- `GET /admin/bot/api/syndication/sources`
- `POST /admin/bot/api/syndication/sources/{source_id}/retry`

This keeps the first control-room pass aligned with the highest-value operator workflows while leaving room for Sync and Audit APIs to grow later.

### Control Room Backend Decision

Current decision:

- Build the first control-room backend inside the existing Flask app.
- Mount it under dedicated `/admin/bot` routes and separate templates from editorial CMS pages.
- Keep auth/session policy separate from current editorial login; use Discord OAuth for operator identity.
- Treat the Flask-hosted control room as an operator shell over explicit bot/admin service boundaries, not as the new owner of bot business logic.

Guardrails:

- Control-room routes should call explicit service/repository boundaries or internal bot/admin APIs, not reach into Discord gateway code directly.
- New operator pages should stay under a distinct template namespace so editorial and ops UI do not drift together accidentally.
- Operator auth, audit logging, and permission checks should be modeled independently from the current single-user editorial admin.
- If live status, websocket needs, or release cadence start fighting the website shell, extraction to a separate surface becomes the next architectural step rather than a redesign.

#### Initial `/admin/bot` Route Map And Template Namespace

Even in the embedded-first phase, the control room should behave like a separate application slice.

Recommended Flask structure:

- Add a dedicated `admin_bot` blueprint mounted at `/admin/bot` rather than extending the current editorial handlers inline.
- Keep HTML pages under `website/templates/admin/bot/`.
- Keep operator APIs under `/admin/bot/api/*` and out of Jinja page routes.
- Use a dedicated base template such as `admin/bot/_bot_base.html` so bot ops navigation, auth chrome, and alerts can evolve without editing the editorial CMS shell.

Suggested first page route map:

| Route                                    | Purpose                                             | Initial template                    | Backing API dependencies                                                                                              |
| ---------------------------------------- | --------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `GET /admin/bot`                         | Control-room landing / overview redirect target     | `admin/bot/index.html`              | `GET /admin/bot/api/health`, summary queue/syndication reads                                                          |
| `GET /admin/bot/health`                  | Runtime and dependency health screen                | `admin/bot/health.html`             | `GET /admin/bot/api/health`, `GET /admin/bot/api/health/services`, `GET /admin/bot/api/health/jobs`                   |
| `GET /admin/bot/queues`                  | Queue list and active queue summary                 | `admin/bot/queues.html`             | `GET /admin/bot/api/queues`                                                                                           |
| `GET /admin/bot/queues/<queue_id>`       | Queue detail and moderator action surface           | `admin/bot/queue_detail.html`       | `GET /admin/bot/api/queues/{queue_id}`, `GET /admin/bot/api/queues/{queue_id}/events`                                 |
| `GET /admin/bot/mileage`                 | Mileage search and user summary table               | `admin/bot/mileage.html`            | `GET /admin/bot/api/mileage/users`, `GET /admin/bot/api/mileage/tiers`                                                |
| `GET /admin/bot/mileage/<user_id>`       | Mileage user detail and ledger drill-down           | `admin/bot/mileage_detail.html`     | `GET /admin/bot/api/mileage/users/{user_id}`, `GET /admin/bot/api/mileage/users/{user_id}/events`                     |
| `GET /admin/bot/syndication`             | Source list and status dashboard                    | `admin/bot/syndication.html`        | `GET /admin/bot/api/syndication/sources`                                                                              |
| `GET /admin/bot/syndication/<source_id>` | Source checkpoint, delivery, and retry detail       | `admin/bot/syndication_detail.html` | `GET /admin/bot/api/syndication/sources/{source_id}`, `GET /admin/bot/api/syndication/sources/{source_id}/deliveries` |
| `GET /admin/bot/sync`                    | Cross-system sync visibility                        | `admin/bot/sync.html`               | future sync/read-model endpoints                                                                                      |
| `GET /admin/bot/audit`                   | Audit log search and investigation view             | `admin/bot/audit.html`              | future audit endpoints                                                                                                |
| `GET /admin/bot/login`                   | Operator login start / OAuth handoff page if needed | `admin/bot/login.html`              | Discord OAuth initiation only                                                                                         |

Suggested first API route map:

| Route group                   | Responsibility                                           |
| ----------------------------- | -------------------------------------------------------- |
| `/admin/bot/api/health*`      | Health snapshots, job freshness, dependency state        |
| `/admin/bot/api/queues*`      | Queue read/write operations and queue event history      |
| `/admin/bot/api/mileage*`     | Mileage summaries, ledger reads, adjustments, reversals  |
| `/admin/bot/api/syndication*` | Source status, checkpoints, retries, suppression actions |
| `/admin/bot/api/sync*`        | Shared event/read-model sync visibility and repair hooks |
| `/admin/bot/api/audit*`       | Operator action history and investigation queries        |

Suggested template namespace:

```text
website/templates/
    admin/
        _admin_base.html
        ...existing editorial templates...
        bot/
            _bot_base.html
            _bot_nav.html
            index.html
            login.html
            health.html
            queues.html
            queue_detail.html
            mileage.html
            mileage_detail.html
            syndication.html
            syndication_detail.html
            sync.html
            audit.html
```

Template rules:

- `admin/bot/_bot_base.html` may extend `admin/_admin_base.html` initially for shared static assets, but bot-specific navigation and operator notices should live in bot partials.
- Editorial templates should never import bot partials.
- Bot pages should prefer client-side fetches against `/admin/bot/api/*` for dynamic panels rather than embedding operational logic directly in template rendering.
- Page titles, breadcrumbs, and nav labels should use operator language such as Health, Queues, Mileage, Syndication, Sync, and Audit instead of editorial terms.

#### Operator Auth And Session Boundary

The embedded control room needs a separate auth system even while it shares the Flask process.

Identity source:

- Use Discord OAuth for operator sign-in.
- Treat Discord account identity as authentication only; authorization still depends on local operator policy.
- Do not derive write permissions from arbitrary Discord guild membership alone.

Local operator model:

| Concern           | Initial rule                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Identity key      | Store operator records keyed by Discord user id.                                                                                      |
| Local allowlist   | Maintain an explicit operator allowlist or operator-role mapping in app config or bot-owned tables.                                   |
| Display fields    | Persist safe profile metadata such as username, global name, avatar URL, and last login time.                                         |
| Permission source | Map operators to explicit scopes such as `ops.read`, `queue.write`, `mileage.write`, `syndication.write`, `audit.read`, `sync.write`. |
| Suspension        | Support local disable/suspend state independent of Discord account existence.                                                         |

Recommended session shape:

- Use a distinct session namespace for control-room state, for example keys prefixed with `bot_ops_`.
- Session should store only minimal operator identity and authorization context:
  `bot_ops_user_id`, `bot_ops_session_id`, `bot_ops_scopes`, `bot_ops_login_at`, and `bot_ops_last_seen_at`.
- Do not store Discord access tokens in the Flask signed session cookie.
- Keep OAuth tokens server-side only if they are actually needed after login; otherwise discard them after identity verification.

Cookie and request boundary rules:

- Do not reuse the editorial admin login cookie as proof of operator identity.
- If a shared Flask session cookie remains in place technically, treat control-room auth as a separate logical session with its own required keys and guards.
- Apply dedicated decorators or request guards for `/admin/bot` and `/admin/bot/api/*` instead of piggybacking on the current editorial `before_request` login check.
- Operator API routes should return `401` or `403` JSON responses; page routes may redirect to `/admin/bot/login`.

Suggested auth flow:

| Step | Route / action                  | Result                                                                                              |
| ---- | ------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1    | `GET /admin/bot/login`          | Render operator login page with Discord OAuth start button and safe explanation of required access. |
| 2    | `GET /admin/bot/oauth/start`    | Create CSRF state, redirect to Discord OAuth authorize URL.                                         |
| 3    | `GET /admin/bot/oauth/callback` | Validate state, exchange code, fetch Discord identity, resolve local operator record/scopes.        |
| 4    | Session creation                | Store minimal `bot_ops_*` session data and audit successful login.                                  |
| 5    | `GET /admin/bot`                | Redirect to Overview if operator has `ops.read`; otherwise show denied state.                       |
| 6    | `POST /admin/bot/logout`        | Clear only operator session keys and audit logout without disturbing editorial session state.       |

Authorization rules:

- `ops.read` grants access to overview, health, and basic read-only operational screens.
- Domain write scopes gate mutations:
  `queue.write`, `mileage.write`, `syndication.write`, and `sync.write`.
- `audit.read` should be distinct from general ops read if audit history contains sensitive operator actions.
- High-risk actions such as queue clear, checkpoint reset, and mileage reversal should require both the relevant write scope and explicit confirmation.

Audit and security rules:

- Log login success, login failure, logout, and scope-denied actions in the audit stream.
- Rotate session identifiers on login to reduce fixation risk.
- Set idle timeout shorter for operator sessions than for editorial CMS sessions.
- Protect OAuth start and callback with CSRF/state validation and strict redirect target validation.
- Never expose raw OAuth tokens, Discord guild secrets, or upstream API credentials in rendered pages or JSON payloads.

Initial implementation guidance:

- Start with a simple local operator allowlist backed by config or a bot-owned operator table.
- Keep operator auth decorators, session helpers, and scope checks in dedicated control-room modules rather than mixing them into the existing editorial auth code.
- If the current Flask-Login setup becomes awkward for parallel editorial and operator auth, prefer a separate lightweight operator session helper over forcing both models through one user class.

### Control Room UI Information Architecture

The first control-room UI should optimize for operator triage and intervention, not for content authoring. Whether it initially lives under `/admin/bot` or later moves into a separate surface, the information architecture should stay domain-oriented.

#### Primary Navigation

| Area        | Purpose                                                            | Primary audience              | Default entry conditions                                         |
| ----------- | ------------------------------------------------------------------ | ----------------------------- | ---------------------------------------------------------------- |
| Overview    | Fast operational triage across all bot domains                     | Operators, moderators         | First screen after login                                         |
| Health      | Runtime health, config presence, worker status, failing jobs       | Operators                     | Open when startup, API, or job health is degraded                |
| Queues      | Current queue state, moderator actions, recent queue events        | Moderators, event operators   | Open during active events or queue incidents                     |
| Mileage     | User totals, recent awards, manual adjustments, tier state         | Operators, community managers | Open during disputes, milestone reviews, or event reconciliation |
| Syndication | Source status, checkpoints, retries, recent deliveries             | Operators, content admins     | Open when announcements fail, lag, or duplicate                  |
| Sync        | Website-to-bot shared-data visibility for events and announcements | Operators                     | Open when website edits are not reflected in Discord workflows   |
| Audit       | Sensitive action history and investigation trail                   | Operators, auditors           | Open during incident review or operator troubleshooting          |

#### Overview Screen

Overview should be a summary page, not a dumping ground.

| Region                       | Content                                                                                            | Why it exists                                                                       |
| ---------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Global status strip          | Bot runtime state, API reachability, last successful poll, stale-job count, active incident banner | Lets operators decide in seconds whether the problem is systemic or domain-specific |
| Attention cards              | Queue backlog warning, mileage reconciliation needed, failed syndication retries, sync drift count | Surfaces action-needed states before the operator drills in                         |
| Upcoming operational context | Next screening/event, active queue channel, pending reminders, recent website content updates      | Gives operators context for what should happen next                                 |
| Recent operator actions      | Last manual overrides, retries, queue clears, mileage adjustments                                  | Helps avoid duplicate interventions and improves handoff                            |

#### Domain Screens

| Screen      | Primary panels                                                                                   | Key actions                                                         | Cross-links                |
| ----------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- | -------------------------- |
| Health      | service status summary, dependency/config checks, job execution timeline, recent errors          | acknowledge incident, refresh status, open diagnostics              | Queue, Syndication, Audit  |
| Queues      | active queue snapshot, waiting entries, recent transitions, moderator event log                  | advance, remove, reorder, pause, clear queue                        | Overview, Audit, Sync      |
| Mileage     | user search, totals table, recent mileage events, adjustment history, tier thresholds            | grant adjustment, reverse event, inspect user history               | Audit                      |
| Syndication | source list, checkpoint table, delivery history, retry failures, suppression/dedup signals       | retry source, disable source, reset checkpoint, inspect payload     | Audit, Sync                |
| Sync        | website event/read-model status, stale projection list, last sync results, unresolved mismatches | re-run sync, inspect source DTO, mark issue acknowledged            | Queues, Syndication, Audit |
| Audit       | filters by actor/domain/action, chronological audit stream, action detail drawer                 | export filtered log, inspect linked object, jump to affected domain | All other screens          |

#### Detail And Drill-Down Patterns

Use consistent drill-down behavior across domains:

- Table/list on the left or top for fast scanning.
- Detail drawer or side panel for the selected object.
- Action bar scoped to the selected object only.
- Embedded timeline for state transitions or retries.
- Links back to related domain objects instead of copying the same data into multiple screens.

Examples:

- Queue entry detail should show current position, join timestamp, actor history, and the last moderator action.
- Mileage user detail should show total points, event ledger, manual corrections, and current tier status.
- Syndication source detail should show the last checkpoint, last successful delivery, recent failures, and dedup state.

#### Shared UX Rules

- Prefer read-first workflows with explicit confirmation for destructive actions.
- Put global search and filters near the top of Queue, Mileage, Syndication, and Audit screens.
- Show timestamps in UTC plus localized operator display where possible.
- Mark manual overrides visually so they stand out from automated system actions.
- Keep secrets and raw tokens out of operator views; expose only config presence and safe metadata.
- Design for desktop first, but keep layout workable on smaller laptop screens used during live events.

#### MVP Control Room Release Order

1. Overview
2. Health
3. Queues
4. Syndication
5. Audit
6. Mileage
7. Sync

Reasoning:

- Overview and Health are needed before deeper ops tooling is trustworthy.
- Queue and Syndication are the highest-likelihood early operational workflows.
- Audit should ship before heavy manual controls expand.
- Mileage and Sync can follow once the underlying bot domains are live enough to operate.

Ownership principle should stay constant even if route names move later: control-room pages speak to ops APIs; ops APIs speak to bot services and owned persistence layers.

### Planned Deployment Model

Preferred deployment topology:

- Website deploys independently as current Flask web app.
- Bot deploys independently as long-lived worker/service.
- Control room deploys independently as SPA or thin web surface backed by ops APIs.

Why split deploys:

- Website content releases should not require bot restart.
- Bot incidents should not block public-site publishing.
- Control-room UI can iterate without tying changes to public-site shell.

### Near-Term And Long-Term Path

Near term:

- Keep current Flask admin as editorial CMS.
- Do not overload it with bot runtime concerns.

Immediate follow-up work implied by this architecture:

- Scaffold bot package and runtime entrypoint
- Define DB ownership and migration plan for bot tables
- Repair current pytest environment so website baseline remains verifiable, move existing tests into `tests/website/` subfolder
- Document env matrix and ADRs for split-surface architecture

Long term:

- Build dedicated control-room UI for bot and cross-system operations.
- Expose only explicit, authenticated read/write operations through service APIs or controlled DB read models.

### Boundary Guidance

- Website should continue owning public content, SEO, and editorial workflows.
- Future bot should own Discord-native automation and community state.
- Shared data should move through explicit DB contracts or shared domain modules, not template-layer coupling.

## 12. Glossary

| Term          | Definition                                                                     |
| ------------- | ------------------------------------------------------------------------------ |
| Public site   | Customer-facing Open Mic Odyssey website                                       |
| Admin CMS     | Protected Flask admin routes for editing site content                          |
| Content store | Logical read/write layer behind movie, people, media, FAQ, and related content |
| Static export | Rendered flat-file output generated from public Flask routes                   |
| JSON-LD       | Structured schema.org metadata injected into rendered pages                    |
| Control room  | Planned broader operations dashboard beyond current editorial CMS              |
