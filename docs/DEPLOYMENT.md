# Deployment Guide

This document is the source of truth for deployment across the current Flask website, the embedded `/admin/bot` control room, and the planned Discord bot worker.

## Current reality

- The website is deployable today and is the only production-ready runtime in this repository.
- The control room currently ships inside the same Flask app under `/admin/bot`; it is not a separate deployable service yet.
- The bot worker has a Python scaffold and startup entrypoint, but it is still a planned operational surface rather than a production-ready runtime.

Use this guide to keep deployment planning aligned with the code that exists now, while still documenting the intended split-service topology.

## Service matrix

| Surface                       | Current status       | Source path                | Runtime entrypoint                                 | Public port / route | Notes                                                      |
| ----------------------------- | -------------------- | -------------------------- | -------------------------------------------------- | ------------------- | ---------------------------------------------------------- |
| Website                       | Deployable now       | `website/`                 | `gunicorn app:app --bind 0.0.0.0:8000 --workers 2` | `8000`              | Current production baseline                                |
| Embedded control room         | Deploys with website | `website/`                 | same Flask process as website                      | `/admin/bot`        | Separate operator auth, same web resource                  |
| Bot worker                    | Scaffold only        | repo root + `bot/omo_bot/` | `python -m bot.omo_bot`                            | none                | Long-running worker, no public HTTP surface documented yet |
| Extracted control-room UI/API | Future only          | not implemented            | not implemented                                    | not implemented     | Keep as planned topology, not current runtime fact         |

## Recommended topology

### Phase 1: current recommended deployment

Deploy one web resource for the website and embedded control room.

```txt
┌──────────────────────┐      HTTPS       ┌──────────────────────────────┐
│ Public visitors      │◄────────────────►│ Website web resource         │
│ Editors              │                  │ Flask + Gunicorn             │
│ Bot operators        │                  │ public pages + /admin +      │
└──────────────────────┘                  │ /admin/bot                   │
                                          └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────────┐
                                              │ PostgreSQL              │
                                              └─────────────────────────┘
```

This is the only deployment mode that matches the repo’s implemented surfaces today.

### Phase 2: planned split-service topology

When the bot worker matures beyond the current scaffold, deploy it independently from the website.

```txt
┌──────────────────────┐      HTTPS       ┌──────────────────────────────┐
│ Public visitors      │◄────────────────►│ Website web resource         │
│ Editors              │                  │ Flask + Gunicorn             │
│ Bot operators        │                  │ public pages + /admin +      │
└──────────────────────┘                  │ /admin/bot (embedded first) │
                                          └──────────────┬───────────────┘
                                                         │
                                                         │ shared DB
                                                         ▼
                                              ┌─────────────────────────┐
                                              │ PostgreSQL              │
                                              └─────────────┬───────────┘
                                                            │
                                                            ▼
                                              ┌─────────────────────────┐
                                              │ Bot worker resource     │
                                              │ python -m bot.omo_bot   │
                                              └─────────────────────────┘
```

### Phase 3: optional extracted control room

If `/admin/bot` outgrows the embedded-first phase, extract the operator UI/API into its own resource later. That surface is still future work and should not be documented as current runtime fact.

## Website deployment

The current website deployment path remains Coolify + Nixpacks.

### Coolify resource settings

| Setting                | Value                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| Resource type          | Application                                                                                      |
| Base directory         | `website` when deploying from this repo, or `/` when using a mirror repo rooted at the Flask app |
| Build pack             | Nixpacks                                                                                         |
| Build command          | leave empty                                                                                      |
| Start command          | `gunicorn app:app --bind 0.0.0.0:8000 --workers 2`                                               |
| Port                   | `8000`                                                                                           |
| Suggested health check | `/robots.txt`                                                                                    |

### Website environment

Use the website and control-room sections in [ENVIRONMENT.md](/docs/ENVIRONMENT.md).

Minimum production set:

- `SITE_URL`
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`

Add these when operator login is enabled in the embedded control room:

- `OMO_DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI`

### Website deployment checklist

- Set a real `SECRET_KEY`
- Set a strong `ADMIN_PASSWORD_HASH`
- Set `SITE_URL` to the live canonical URL
- Confirm `DATABASE_URL` points at the intended PostgreSQL instance
- Verify `/`, `/admin`, and `/admin/bot` all respond as expected after deploy

## Embedded control room deployment

The embedded control room is not a second web service today. It deploys automatically with the website because it is registered in the same Flask app.

Operational implications:

- No separate build or release step is needed today
- Operator auth depends on the website’s Flask session secret and the control-room Discord OAuth env vars
- `/admin/bot` failures should be treated as website-web-resource regressions, not separate service incidents

Suggested post-deploy checks:

- `/admin/bot/login` renders
- `/admin/bot/api/health` returns the expected shape when authenticated or the expected auth error when not
- Discord OAuth callback configuration matches the deployed domain

## Bot worker deployment

The bot worker is not production-ready yet, but the planned runtime command already exists.

### Planned worker command

From the repository root:

```powershell
python -m bot.omo_bot
```

### Planned worker resource shape

| Setting        | Recommended value                  |
| -------------- | ---------------------------------- |
| Resource type  | Long-running application or worker |
| Base directory | `/`                                |
| Start command  | `python -m bot.omo_bot`            |
| Public port    | none required                      |
| Restart policy | enabled                            |

### Worker environment

Use the bot-worker section in [ENVIRONMENT.md](/docs/ENVIRONMENT.md).

Minimum worker set:

- `OMO_DISCORD_TOKEN`
- `DATABASE_URL` or `OMO_DATABASE_URL`

Recommended additions when the worker becomes operational:

- `OMO_DISCORD_GUILD_ID`
- `OMO_DISCORD_CHANNEL_MAP`
- `OMO_SYNDICATION_SOURCES`
- `OMO_SYNDICATION_POLL_SECONDS`
- `OMO_LOG_LEVEL`

### Current limitation

Do not describe the worker as production-ready in operational docs yet. The scaffold has config and startup lifecycle coverage, but it does not yet represent a feature-complete Discord automation service.

## Deployment independence rules

These rules matter once the bot worker is deployed separately, and they already apply to migration planning now.

- Website deploys must remain possible without a simultaneous bot rollout.
- Bot deploys must not require a same-minute website rollout.
- Shared PostgreSQL migrations must preserve compatibility windows between website-owned and bot-owned surfaces.
- The public website must not depend on bot-owned tables for correctness.
- The embedded control room may read bot-owned operational data later, but website page rendering should stay independent of worker availability.

## Release order guidance

### Current repo state

1. Deploy database changes first when they are additive and backward compatible.
2. Deploy the website resource.
3. Verify public pages, admin login, and `/admin/bot` health/auth paths.

### Future split-service state

1. Deploy additive database changes first.
2. Deploy the website resource.
3. Deploy the bot worker resource.
4. Verify worker startup and website/control-room compatibility.
5. If a separate control-room service exists later, deploy it last.

## Post-deploy smoke checks

### Website

- `GET /` returns `200`
- `GET /robots.txt` returns `200`
- `GET /sitemap.xml` returns `200`
- `/admin/login` renders

### Embedded control room

- `/admin/bot/login` renders
- OAuth start route redirects when configured
- Operator-only health pages and APIs behave as expected

### Bot worker

- Process starts without config parsing errors
- Logs show runtime startup completed
- Process remains alive under the supervisor or platform restart policy

## Related docs

- [ARCHITECTURE.md](/docs/ARCHITECTURE.md)
- [ENVIRONMENT.md](/docs/ENVIRONMENT.md)
- [TESTING.md](/docs/TESTING.md)
- [DEPLOYMENT_COOLIFY.md](/.github/instructions/DEPLOYMENT_COOLIFY.md)

Current CI workflow already prints sanitized response snippets for deploy failures and tries auth/method fallback variants in `.gitea/workflows/ci-cd.yml`.
