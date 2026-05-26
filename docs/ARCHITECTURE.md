# Open Mic Odyssey Architecture

## 1. Overview

Open Mic Odyssey currently ships as four service surfaces around one shared PostgreSQL database: public website, control room, bot API, and bot worker. Public site lives at `openmicodyssey.com`.

Current repository contains a standalone control room for editorial CMS routes at `/` and `/content/*`, backed by Flask-Login and local admin credentials or seeded DB users. Repository also contains a standalone bot API for operator routes under `/bot`, with Discord OAuth operator login, operator/session management, health/config/command views, and syndication, queue, mileage, onboarding, and moderation APIs. Bot runtime remains a separate worker focused on configuration, startup lifecycle, and YouTube-first syndication polling. It still does **not** contain a feature-complete Discord gateway automation worker or a separate operator dashboard SPA.

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
- [ADR-004: Extract Bot API Into Standalone Service](adr/ADR-004-extract-bot-api-into-standalone-service.md)

### Service Boundary Change Checklist

When route ownership, auth ownership, deployment topology, or service responsibilities change, update these docs in the same change:

- `docs/ARCHITECTURE.md` for service boundaries, ownership, and runtime responsibilities
- `docs/DEPLOYMENT.md` for topology, env vars, domains, and health checks
- `docs/TESTING.md` for affected test files, service names, and verification commands
- related ADRs and `CHANGELOG.md` when the boundary change is architectural rather than just wording cleanup

### Stakeholders

| Role                      | Expectation                                              |
| ------------------------- | -------------------------------------------------------- |
| Site owner                | Stable public film website and manageable deploy flow    |
| Editors/admins            | Simple authenticated forms for updating site content     |
| Audience                  | Fast public pages, clear calls to watch/support/connect  |
| Future community ops team | Path to add Discord automation without replacing website |

## 2. Service Boundaries

The codebase is split into four primary services with distinct responsibilities:

### Website (`website/`)

- **Role**: Public Frontend.
- **Responsibility**: Page rendering, SEO/schema output, static site export, and robots/sitemap generation.
- **Data Access**: Read-only access to content via `shared/`.
- **Authentication**: None. All routes are public (except internal/hidden map route).

### Control Room (`control_room/`)

- **Role**: Editorial CMS.
- **Responsibility**: Editorial CRUD, dashboard/navigation for site content, and authenticated server-rendered admin forms.
- **Data Access**: Read-write access to editorial content.
- **Authentication**: Flask-Login with local password verification, seeded DB users, and role assignments.

### Bot API (`bot_api/`)

- **Role**: Operator Dashboard & Ops API.
- **Responsibility**: Discord OAuth operator login, bot health/config/command views, queue/mileage/onboarding/moderation endpoints, syndication controls, and **Discord API polling** for guild/channel/role enrichment.
- **Data Access**: Read-write access to bot-specific tables and read-only access to shared content where needed. Fetches live Discord guild metadata via bot token auth.
- **Authentication**: Discord OAuth plus locally managed operator scopes.
- **Logging**: Structured `logging.getLogger(__name__)` across all route modules, runtime snapshot builders, and bot worker bootstrap code. Logs config parsing, repository wiring, operator actions, and syndication events.

### Bot Worker (`bot/`)

- **Role**: Automation Worker.
- **Responsibility**: Background runtime, event polling, syndication jobs, and future Discord gateway automation.
- **Data Access**: Read-write access to bot-specific tables and read-only access to movie content.

## 3. Scope

### Current In Scope

- Flask website runtime in `website/`
- Public pages, compatibility redirects, sitemap, robots, and hidden map route
- Standalone control room runtime in `control_room/`
- Editorial CMS dashboard routes at `/` plus content routes under `/content/*` on the control room service
- Local username/password login plus seeded DB user and role tables for editorial admin access
- Standalone bot API runtime in `bot_api/`
- Operator routes, templates, and ops APIs under `/bot/*` on the bot API service
- Discord OAuth operator login for the bot API
- PostgreSQL-backed content read/write layer
- JSON-LD schema generation from structured content
- Static export generation to `website/dist`
- Coolify/Nixpacks website deployment configuration
- Bot scaffold runtime in `bot/` for config parsing, startup lifecycle, operator-facing health/config inspection, and syndication polling seams
- Bot-owned operator and syndication persistence seams backed by PostgreSQL migrations
- Discord API fetchers for guild metadata, channel list, and role list via bot token auth, enriching the bot config snapshot
- Structured logging with `logging.getLogger(__name__)` across bot worker (`config.py`, `main.py`) and bot API (`admin_bot.py`, `runtime_snapshot.py`, all route modules)
- Operator health endpoint (`GET /bot/api/operator-health`) combining health status, syndication snapshot, queue index, and diagnostics

### Current Out Of Scope

- Feature-complete Discord gateway automation worker
- Queue, mileage / XP, onboarding, and moderation domains
- Separate React/Vite dashboard application
- Native mobile applications

### Known Documentation / Code Gap

Documentation and config mention `DATA_SOURCE=JSON` fallback, but current `website/movie_site/content_store.py` factory always returns DB-backed reader/writer. Architecture must treat DB-backed content as current implemented path.

## 4. Context

### Current System Context

Public visitors interact with a public Flask website deployed at openmicodyssey.com. Editors interact with a separate Flask control room deployed at admin.openmicodyssey.com. Bot operators interact with a standalone bot API surface deployed at api.openmicodyssey.com. Website, control room, bot API, and bot worker share one PostgreSQL database. The bot worker runs as a separate process for config validation and syndication polling seams.

### Future-State Context

Four independent services share one PostgreSQL database:

- **Website** (openmicodyssey.com) serves public pages on port 8880.
- **Control Room** (admin.openmicodyssey.com) provides editorial login and CMS routes on port 8480.
- **Bot API** (api.openmicodyssey.com) exposes operator pages plus health, queue, mileage, onboarding, moderation, syndication, and bot management endpoints on port 8787.
- **Bot Worker** runs as a separate long-lived process with no public HTTP surface.

All traffic routes through Nginx Proxy Manager on the Coolify server. The Discord bot worker connects to Discord's gateway API and reads/writes bot-owned tables in the shared database.

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
│ Configuration                                               │
│  └─ movie_site/config.py                                   │
│                                                            │
│ Data / Logic (Delegated to shared/)                         │
│  ├─ shared/movie_data.py                                   │
│  ├─ shared/content_store.py                                │
│  ├─ shared/schema.py                                       │
│  └─ shared/db.py                                           │
│                                                            │
│ Export + assets                                             │
│  ├─ website/export_static.py                               │
│  ├─ website/templates/                                     │
│  └─ website/static/                                        │
└───────────────────────────────┬────────────────────────────┘
                                │
                                ▼
                     ┌────────────────────────┐
                     │ PostgreSQL + file env  │
                     └────────────────────────┘
```

### Current Building Blocks

- `website/app.py`: thin WSGI entrypoint exposing `app`.
- `website/movie_site/__init__.py`: public website app factory, config loading, and public blueprint registration.
- `website/movie_site/views.py`: public routes, page context, meta tags, sitemap, robots, and hidden map page.
- `website/movie_site/config.py`: environment-driven defaults and secrets/config.
- `control_room/app.py`: control-room app factory, auth wiring, and blueprint registration.
- `control_room/admin.py`: editorial login/logout, dashboard entry, and top-level auth guard.
- `control_room/content.py`: editorial CMS route definitions under `/content/*`.
- `control_room/admin_content.py`: CRUD handlers for film, media, content, events, FAQ, people, connect, reviews, and assets.
- `control_room/auth.py`: Flask-Login admin user model and role checks for editorial CMS.
- `control_room/user_repo.py`: editorial user lookup, creation, password verification, and role assignment.
- `bot_api/app.py`: bot API app factory, config loading, blueprint registration, and health/config endpoints.
- `bot_api/admin_bot.py`: operator routes, Discord OAuth flow, and bot ops pages and APIs.
- `shared/db.py`: connection-pool helper functions using `psycopg2`.
- `shared/content_store.py`: content store factory abstraction and read/write implementations.
- `shared/movie_data.py`: aggregates content records into a page-ready data model.
- `shared/schema.py` plus `parts/`: builds the JSON-LD graph for SEO/schema.org output.
- `website/export_static.py`: renders public routes into static HTML and validates output.

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

Control room routes in current code:

- `/`
- `/login`
- `/logout`
- `/content`
- `/content/film`
- `/content/media`
- `/content/content`
- `/content/events`
- `/content/faq`
- `/content/people`
- `/content/connect`
- `/content/connect/social`
- `/content/connect/supporters`
- `/content/connect/patreon`
- `/content/media-assets`
- `/content/reviews`
- `/content/submissions`

Bot API routes in current code:

- `/health`
- `/api/config`
- `/oauth/discord/callback`
- `/bot`
- `/bot/login`
- `/bot/oauth/start`
- `/bot/health`
- `/bot/onboarding`
- `/bot/moderation`
- `/bot/operators`
- `/bot/syndication`
- `/bot/config`
- `/bot/commands`
- `/bot/mileage`
- `/bot/queues`
- `/bot/api/health`
- `/bot/api/health/services`
- `/bot/api/health/jobs`
- `/bot/api/operator-health`
- `/bot/api/queues`
- `/bot/api/mileage/users`
- `/bot/api/syndication/sources`

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

Editorial CMS remains a server-rendered Flask surface. Bot operator tooling is served by the separate `bot_api/` Flask app rather than the CMS shell.

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

1. Editor requests `/` or `/content/*` on the control room service.
2. `before_request` guard redirects unauthenticated user to `/login`.
3. Login form first resolves a DB-backed admin user by username.
4. Password is verified against the stored Werkzeug hash; legacy config-based fallback remains available.
5. Flask-Login stores session and redirects back to the requested CMS route.

### Scenario: Admin Content Edit (Control Room)

1. Authenticated editor submits form to a control-room `/content/*` route.
2. `control_room/content.py` delegates to a handler in `control_room/admin_content.py`.
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

### Scenario: Operator Login (Bot API)

1. Operator requests `/bot/login` on bot API service (port 8787).
2. Bot API renders Discord OAuth start button.
3. Operator authorizes via Discord; callback returns to the configured bot API OAuth callback.
4. Bot API validates OAuth state, fetches Discord identity, and resolves the local operator record.
5. Bot API creates an operator session with scoped permissions (`ops.read`, `queue.write`, etc.).
6. Operator is redirected to `/bot`.

### Scenario: Bot Health Check (Bot API)

1. Operator opens `/bot/health` on the bot API service.
2. Bot API page or client-side fetch calls `GET /bot/api/health` on the same service.
3. Bot API returns runtime state, DB reachability, job freshness, and config presence.
4. The operator health dashboard renders status indicators from that payload.
5. For a combined view, operators can call `GET /bot/api/operator-health` (scope: `ops.read`) which merges health component statuses, syndication snapshot, queue index, and diagnostics into a single response.

### Scenario: Discord API Polling (Bot API Config View)

1. Operator opens `/bot/config` on the bot API service.
2. `build_bot_configuration_snapshot()` calls `build_discord_guild_snapshot(guild_id)`.
3. Bot API fetches guild metadata, channel list, and role list from Discord's REST API using the bot token (`OMO_DISCORD_TOKEN`).
4. Results are cached per-request and included in the config snapshot.
5. The config template displays guild name, member count, features, channel list, and role list.
6. If the bot token or guild ID is missing, the section shows a clear "unavailable" message.

### Scenario: Syndication Polling (Bot Worker)

1. Bot worker starts, loads config from env and DB.
2. Syndication polling job runs on configured interval (default 300s).
3. Job queries YouTube adapter for new content since last checkpoint.
4. New items are normalized and posted to configured Discord channels.
5. Checkpoint updated in `bot_syndication_checkpoint` table.
6. Bot operators can inspect source status and trigger retries via the bot API.

### Scenario: Queue Management (Bot API)

1. Moderator opens `/bot/queues` on the bot API service.
2. Bot API fetches queue list from `GET /bot/api/queues`.
3. Moderator advances queue via `POST /bot/api/queues/{queue_id}/advance`.
4. Bot API validates scope (`queue.write`), updates queue state, emits audit entry.
5. Bot API refreshes the queue detail view with updated state.

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

PostgreSQL is always available at `192.168.88.35`. All four service surfaces connect to the same database instance with separate table ownership:

- Website owns editorial tables (`movie`, `gallery_item`, `faq_item`, etc.)
- Control room writes editorial data through the shared content store and admin user tables
- Bot API and bot worker own operational tables (`bot_guild_config`, `bot_queue`, `bot_mileage_event`, `bot_syndication_source`, etc.)
- Shared integration tables exist for cross-surface read models

### Coolify Deployment

Each service deploys as an independent Coolify Application resource:

| Service      | Base Directory  | Start Command                                     | Port | Health Check      |
| ------------ | --------------- | ------------------------------------------------- | ---- | ----------------- |
| Website      | `website/`      | `waitress-serve --port 8880 website.app:app`      | 8880 | `GET /robots.txt` |
| Control Room | `control_room/` | `waitress-serve --port 8480 control_room.app:app` | 8480 | `GET /login`      |
| Bot API      | `bot_api/`      | `waitress-serve --port 8787 bot_api.app:app`      | 8787 | `GET /health`     |
| Bot Worker   | `/` (repo root) | `python -m bot`                                   | none | process alive     |

### Nginx Proxy Manager

Nginx Proxy Manager is pre-configured with proxy hosts for all public HTTP domains. Each proxy host:

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
- Control room `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and DB-backed admin user records govern editorial CMS session auth.
- `BOT_API_URL` lets the control room link out to the standalone bot operator surface.
- Bot API `SECRET_KEY` plus `BOT_OPS_DISCORD_*` values govern Discord OAuth operator sessions.
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
- `ADMIN_PASSWORD`
- `OMO_BOT_API_URL`
- `OMO_DISCORD_CLIENT_ID` / `DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET` / `DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI` / `DISCORD_REDIRECT_URI`

### Bot API Required Environment Variables

- `SECRET_KEY`
- `DATABASE_URL` or `OMO_DATABASE_URL`

### Bot API Optional Environment Variables

- `OMO_DISCORD_TOKEN` / `DISCORD_TOKEN` — used for Discord API fetches (guild, channels, roles) and bot runtime config
- `OMO_DISCORD_GUILD_ID`
- `OMO_SYNDICATION_SOURCES`
- `OMO_SYNDICATION_POLL_SECONDS`
- `OMO_LOG_LEVEL`
- `OMO_DISCORD_CLIENT_ID` / `DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET` / `DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI` / `DISCORD_REDIRECT_URI`
- `OMO_BOT_OPS_ALLOWED_USER_IDS`
- `OMO_BOT_OPS_DEFAULT_SCOPES`

### Testing Notes

Tests should not rely on a live database connection. Use in-memory repositories or mocked DB layers for test execution. The PostgreSQL instance at `192.168.88.35` is for production/runtime use only.

## 8. Security And Operations

### Current Security Model

- Public site is anonymous-read.
- Admin CMS uses Flask session auth with configured credentials or DB-backed admin users and roles.
- Bot API operator auth uses Discord OAuth plus locally managed operator scopes and session idle timeout rules.
- Secrets are environment-based.
- Hidden `/map` page still depends on public Mapbox token for client-side rendering.

### Current Operational Characteristics

- App is a small modular Flask/Python codebase with public website, editorial CMS, standalone bot API, and standalone worker surfaces.
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
- Bot API operator auth uses Discord OAuth plus local scope checks, not website or control-room session cookies.
- Control room editorial auth and bot operator auth are intentionally separate and should remain so.
- Bot worker runtime uses service-level config and secrets rather than browser session state.

Confirmed near-term product decision:

- Keep Discord OAuth as the bot operator authentication path for the standalone `bot_api/` service.
- Keep authorization local through explicit operator scopes rather than Discord guild membership alone.
- Do not converge bot operator auth with the editorial CMS credential model.
- Keep onboarding and role-automation operator workflows on the same Discord-OAuth-backed operator boundary instead of introducing a second auth system first.

### Deployment Relationship

- Website remains independently deployable on Coolify as web app.
- Control room remains independently deployable as the editorial CMS.
- Bot API is independently deployable as the operator-facing web/API surface.
- Current bot scaffold already runs as a separate process, and the future bot should mature into a long-lived worker/service process.
- Shared database migrations must preserve subsystem ownership to avoid one surface breaking another during deploy.

Post-stability revisit outcome:

- Keep the editorial CMS and bot operator surface deployed separately.
- Revisit a separate SPA only if operator workflows create clear pressure for richer realtime UX or a distinct frontend stack.
- Preserve `/bot/api/*` as the operator API seam so later frontend changes remain incremental instead of a rewrite.

### Current Bot Status And Planned Discord Bot

Implemented today:

- bot runtime config parsing and env loading
- runtime startup and shutdown lifecycle scaffold
- YouTube-first syndication adapter, repository, and polling job seams
- standalone bot API operator auth, health/config/commands pages, and syndication actions
- standalone bot API queue, mileage, onboarding, moderation, and diagnostics routes
- bot operator and syndication persistence migrations
- Discord API fetchers for guild metadata, channels, and roles via bot token auth
- structured logging across bot worker and bot API modules
- operator health endpoint (`GET /bot/api/operator-health`) combining health, syndication, queue, and diagnostics

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
    __init__.py
    __main__.py
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

Alternative naming such as `src/bot/` is also acceptable, but bot code should stay isolated from `website/` package boundaries.

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

### Current Control Surfaces

The repo now separates editorial tooling from operator tooling.

- `control_room/` owns editorial login, dashboard navigation, and CMS routes for website content.
- `bot_api/` owns operator login, operator HTML pages, and machine-readable ops endpoints under `/bot/api/*`.
- `bot/` remains the worker/runtime surface and should continue to own background execution rather than browser-facing routes.

### Control Room Scope

Current control room scope is intentionally narrow.

Primary responsibilities:

- Editorial login/logout and admin landing page
- Content editing for film, media, events, FAQ, people, connect, reviews, assets, and submissions
- Linking operators out to the standalone bot API surface when they need bot operations

Should remain outside control-room scope:

- Bot health and runtime dashboards
- Queue, mileage, onboarding, moderation, and syndication operations
- Direct Discord OAuth operator login
- Direct Discord gateway ownership

### Dashboard Architecture Options

Current implemented direction is the separated surface approach.

- Control Room: server-rendered Flask CMS for editorial workflows. It keeps content editing simple, but intentionally excludes bot ops.
- Bot API: standalone Flask operator UI plus JSON APIs under `/bot` and `/bot/api/*`. It keeps auth and deploy boundaries cleaner, but duplicates some shell concerns.

Next revisit trigger:

- Re-evaluate a separate SPA only if operator workflows outgrow server-rendered templates or need richer realtime behavior.

### Planned API Boundaries

Control surfaces should talk to backend service boundaries, not directly to Discord gateway code.

Preferred API split:

- Website CMS APIs remain optional and narrow, only for shared editorial or sync tasks.
- Bot API owns queue controls, mileage adjustments, syndication controls, health endpoints, and ops read models.
- Control room links to the bot API rather than proxying or embedding its operator session.

### Ops API Surface

Operator-facing endpoints now live on the standalone bot API service under `/bot/api/*`. HTML pages stay under `/bot/*`; API routes return machine-readable data only.

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

- `GET /bot/api/health`: overview health snapshot for the operator landing page. Returns bot runtime status, bot API reachability, job freshness, config presence, and degraded domains.
- `GET /bot/api/health/services`: dependency-level detail. Returns Discord connectivity state, DB reachability, scheduler state, and background worker status.
- `GET /bot/api/health/jobs`: background job execution status. Returns last run, next run, last success, consecutive failures, and stale flags per job.
- `POST /bot/api/health/incidents/{incident_id}/acknowledge`: marks an active incident acknowledged. Returns updated incident state and actor metadata.

Health payload should be optimized for operator triage, not low-level metrics dumping.

#### Queue Endpoints

- `GET /bot/api/queues`: lists queues by guild, event, or channel with summary status.
- `GET /bot/api/queues/{queue_id}`: returns queue detail with metadata, ordered entries, moderator flags, and last transition summary.
- `GET /bot/api/queues/{queue_id}/events`: returns paginated queue history in stable reverse-chronological order.
- `POST /bot/api/queues/{queue_id}/advance`: advances the active queue and returns the updated snapshot plus transition summary.
- `POST /bot/api/queues/{queue_id}/entries/{entry_id}/remove`: removes a queued entry and should include a reason in the request body.
- `POST /bot/api/queues/{queue_id}/entries/{entry_id}/move`: reorders an entry and should include the target position.
- `POST /bot/api/queues/{queue_id}/pause`: pauses queue operations and should support a reason or comment.
- `POST /bot/api/queues/{queue_id}/resume`: resumes queue operations.
- `POST /bot/api/queues/{queue_id}/clear`: clears a queue intentionally and should require confirmation and audit logging.

Queue write endpoints should return both current-state data and a lightweight event summary so UI state and audit history stay aligned.

#### Mileage Endpoints

- `GET /bot/api/mileage/users`: searches or lists mileage users with totals, current tier, and recent activity.
- `GET /bot/api/mileage/users/{user_id}`: returns mileage user detail with totals, tier state, recent ledger entries, and pending flags.
- `GET /bot/api/mileage/users/{user_id}/events`: returns paginated mileage event history.
- `POST /bot/api/mileage/users/{user_id}/adjust`: performs a manual mileage adjustment and should include delta, reason, and optional correlation id.
- `POST /bot/api/mileage/events/{event_id}/reverse`: reverses a prior event without deleting history.
- `GET /bot/api/mileage/tiers`: returns tier definitions, thresholds, and counts by tier.

Mileage domain should preserve ledger semantics: no endpoint should hard-delete history that affects totals.

#### Syndication Endpoints

- `GET /bot/api/syndication/sources`: lists configured sources with enabled state, checkpoint, and recent success or failure summary.
- `GET /bot/api/syndication/sources/{source_id}`: returns source detail, checkpoint state, recent deliveries, and dedup information.
- `GET /bot/api/syndication/sources/{source_id}/deliveries`: returns paginated delivery and retry history.
- `POST /bot/api/syndication/sources/{source_id}/retry`: retries failed or pending syndication work.
- `POST /bot/api/syndication/sources/{source_id}/disable`: disables a source and should include a reason or comment.
- `POST /bot/api/syndication/sources/{source_id}/checkpoint/reset`: intentionally resets a checkpoint and should be audited.
- `POST /bot/api/syndication/sources/{source_id}/deliveries/{delivery_id}/suppress`: marks a delivery suppressed or ignored for duplicate control.

Syndication endpoints should expose enough payload metadata for debugging, but should not leak tokens, raw credentials, or unsafe upstream secrets.

#### Suggested MVP Endpoint Set

If the first release needs a smaller scope, start with these:

- `GET /bot/api/health`
- `GET /bot/api/queues`
- `GET /bot/api/queues/{queue_id}`
- `POST /bot/api/queues/{queue_id}/advance`
- `GET /bot/api/mileage/users/{user_id}`
- `POST /bot/api/mileage/users/{user_id}/adjust`
- `GET /bot/api/syndication/sources`
- `POST /bot/api/syndication/sources/{source_id}/retry`

This keeps the first control-room pass aligned with the highest-value operator workflows while leaving room for Sync and Audit APIs to grow later.

### Control Room Backend Decision

Current decision:

- Keep the editorial CMS in `control_room/` and the operator backend in `bot_api/`.
- Mount operator HTML routes under `/bot` and operator JSON routes under `/bot/api/*`.
- Keep auth/session policy separate from editorial login; use Discord OAuth for operator identity.
- Treat the standalone bot API as an operator shell over explicit bot service boundaries, not as the new owner of worker business logic.

Guardrails:

- Operator routes should call explicit service/repository boundaries or worker-facing seams, not reach into Discord gateway code directly.
- Operator pages should stay under a distinct `bot_api/templates/` namespace so editorial and ops UI do not drift together accidentally.
- Operator auth, audit logging, and permission checks should remain independent from editorial admin users.
- If live status, websocket needs, or release cadence outgrow the Flask templates, extraction to a dedicated frontend becomes the next architectural step rather than a redesign.

#### Current `/bot` Route Map And Template Namespace

The bot API should behave like a separate application slice even though it shares the repo and database.

Current Flask structure:

- Use a dedicated `admin_bot` blueprint mounted at `/bot`.
- Keep HTML pages under `bot_api/templates/`.
- Keep operator APIs under `/bot/api/*` and out of Jinja page routes.
- Use a dedicated base template such as `_bot_base.html` so bot ops navigation, auth chrome, and alerts can evolve without editing the editorial CMS shell.

Suggested first page route map:

- `GET /bot`: operator landing or overview redirect target. Uses `index.html` and depends on `GET /bot/api/health` plus summary queue and syndication reads.
- `GET /bot/health`: runtime and dependency health screen. Uses `health.html` and depends on `GET /bot/api/health`, `GET /bot/api/health/services`, and `GET /bot/api/health/jobs`.
- `GET /bot/queues`: queue list and active queue summary. Uses `queues.html` and depends on `GET /bot/api/queues`.
- `GET /bot/queues/<queue_id>`: queue detail and moderator action surface. Uses `queue_detail.html` and depends on `GET /bot/api/queues/{queue_id}` plus `GET /bot/api/queues/{queue_id}/events`.
- `GET /bot/mileage`: mileage search and user summary table. Uses `mileage.html` and depends on `GET /bot/api/mileage/users` plus `GET /bot/api/mileage/tiers`.
- `GET /bot/mileage/<user_id>`: mileage user detail and ledger drill-down. Uses `mileage_detail.html` and depends on `GET /bot/api/mileage/users/{user_id}` plus `GET /bot/api/mileage/users/{user_id}/events`.
- `GET /bot/syndication`: source list and status dashboard. Uses `syndication.html` and depends on `GET /bot/api/syndication/sources`.
- `GET /bot/onboarding`: onboarding config and events view. Uses `onboarding.html` and depends on onboarding read endpoints and event feeds.
- `GET /bot/moderation`: moderation queue and diagnostic surface. Uses `moderation.html` and depends on moderation and diagnostics endpoints.
- `GET /bot/operators`: operator roster and scope visibility. Uses `operators.html` and depends on `GET /bot/api/operators`.
- `GET /bot/config`: bot configuration inspection. Uses `config.html` and depends on `GET /bot/api/config`.
- `GET /bot/commands`: command catalog and runtime help. Uses `commands.html` and depends on `GET /bot/api/commands`.
- `GET /bot/login`: operator login start or OAuth handoff page. Uses `login.html` and depends on Discord OAuth initiation only.

Suggested first API route map:

| Route group             | Responsibility                                           |
| ----------------------- | -------------------------------------------------------- |
| `/bot/api/health*`      | Health snapshots, job freshness, dependency state        |
| `/bot/api/queues*`      | Queue read/write operations and queue event history      |
| `/bot/api/mileage*`     | Mileage summaries, ledger reads, adjustments, reversals  |
| `/bot/api/syndication*` | Source status, checkpoints, retries, suppression actions |
| `/bot/api/onboarding*`  | Onboarding config, role bindings, and event history      |
| `/bot/api/operators*`   | Operator roster, scopes, and access visibility           |
| `/bot/api/diagnostics*` | Runtime diagnostics and troubleshooting payloads         |

Suggested template namespace:

```text
bot_api/templates/
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
    onboarding.html
    moderation.html
    operators.html
    config.html
    commands.html
```

Template rules:

- `bot_api/templates/_bot_base.html` may reuse shared assets, but bot-specific navigation and operator notices should live in bot partials.
- Editorial templates should never import bot partials.
- Bot pages should prefer client-side fetches against `/bot/api/*` for dynamic panels rather than embedding operational logic directly in template rendering.
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
- Apply dedicated decorators or request guards for `/bot` and `/bot/api/*` instead of piggybacking on the control-room editorial `before_request` login check.
- Operator API routes should return `401` or `403` JSON responses; page routes may redirect to `/bot/login`.

Suggested auth flow:

1. `GET /bot/login`: render operator login page with Discord OAuth start button and a safe explanation of required access.
2. `GET /bot/oauth/start`: create CSRF state and redirect to the Discord OAuth authorize URL.
3. `GET /oauth/discord/callback` or configured bot API callback: validate state, exchange code, fetch Discord identity, and resolve local operator scopes.
4. Session creation: store minimal `bot_ops_*` session data and audit successful login.
5. `GET /bot`: redirect to Overview if the operator has `ops.read`; otherwise show a denied state.
6. Logout route: clear only operator session keys and audit logout without disturbing editorial session state.

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
- Keep operator auth decorators, session helpers, and scope checks in dedicated bot API modules rather than mixing them into the editorial auth code.
- If the current Flask-Login setup becomes awkward for parallel editorial and operator auth, prefer a separate lightweight operator session helper over forcing both models through one user class.

### Control Room UI Information Architecture

The operator UI should optimize for triage and intervention, not for content authoring. Now that it lives under the standalone `/bot` surface, the information architecture should stay domain-oriented.

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
