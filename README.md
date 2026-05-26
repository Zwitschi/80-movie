# Movie Project

This project contains materials and code for the "Open Mic Odyssey" movie project.

## Repository Structure

```text
shared/            # Shared modules (db, content store, schema, config, utils)
website/           # Flask web application (public site only)
control_room/      # Flask app for editorial CMS, bot operator login, and ops dashboard
bot_api/           # Flask app for bot health + config endpoints
bot/               # Discord bot worker runtime (scaffold)
deploy/            # Coolify deployment configs per service
database/          # PostgreSQL schema and migrations
docs/              # Architecture, deployment, environment, testing docs
tests/             # Test suite
.env.*.example     # Environment variable templates per service
```

## Services

| Service      | Domain                   | Port | Source          |
| ------------ | ------------------------ | ---- | --------------- |
| Website      | openmicodyssey.com       | 8880 | `website/`      |
| Control Room | admin.openmicodyssey.com | 8480 | `control_room/` |
| Bot API      | api.openmicodyssey.com   | 8787 | `bot_api/`      |
| Bot Worker   | internal                 | none | `bot/`          |

All services share a PostgreSQL database at `192.168.88.35` and run on a single Coolify server behind Nginx Proxy Manager.

## Quick Start

### Website

```bash
cd website
pip install -r requirements.txt
flask run
```

### Control Room

```bash
cd control_room
pip install -r requirements.txt
flask run
```

### Bot API

```bash
cd bot_api
pip install -r requirements.txt
flask run
```

### Bot Worker

```bash
python -m bot
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, topology, ADRs
- [Deployment](docs/DEPLOYMENT.md) — Coolify + Nginx setup steps
- [Environment](docs/ENVIRONMENT.md) — per-service env var reference
- [Nginx](docs/NGINX.md) — proxy host configuration
- [Testing](docs/TESTING.md) — test strategy and coverage

> from [Google Docs](https://docs.google.com/document/d/1T9QmXg7GLwMNTnOL72V16Ry0WEPrJj3ahbCa4TjS6HQ/edit?tab=t.0#heading=h.flei6gybekyw)

```markdown
# Documentary movie website

- Trailer (self hosted/YouTube/Vimeo)
- Embed social media
- Instagram
- TikTok
- YouTube
- Crowdfunding campaign
- Patreon
- credits / links

Photo gallery?

Maybe a page that shows like an interactive map of the stops

A stupid web game lol

Something that says all the content you get from patreon like the main movie, the texas podcast, the just driving footage and music cut, and more. Maybe podcasts recorded on discord or something.
```

## Map Easter Egg

A hidden /map page displays a Mapbox GL JS route visualization of the film's road trip, built from TeslaCam GPS data.

### Access

The map is not listed in the site navigation. A hidden "Route Map" link in the footer becomes visible on hover.

### Configuration

The map requires a Mapbox public access token:

- Create a free account at [mapbox.com](https://www.mapbox.com/) and copy your public token.
- Add it to `website/.env`:

```dotenv
MAPBOX_ACCESS_TOKEN=pk.your_token_here
```

- For the static export deployment, add a `MAPBOX_ACCESS_TOKEN` secret to the GitHub repository.

### Route data

Route points are stored in website/static/data/map_data.json (649 GPS coordinates). The Mapbox GL JS logic lives in website/static/js/map.js.

## Coolify Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full deployment steps. Quick reference:

| Service      | Base Dir        | Start Command                                                   | Port |
| ------------ | --------------- | --------------------------------------------------------------- | ---- |
| Website      | `/` (repo root) | `gunicorn website.app:app --bind 0.0.0.0:8880 --workers 2`      | 8880 |
| Control Room | `/` (repo root) | `gunicorn control_room.app:app --bind 0.0.0.0:8480 --workers 2` | 8480 |
| Bot API      | `/` (repo root) | `gunicorn bot_api.app:app --bind 0.0.0.0:8787 --workers 2`      | 8787 |
| Bot Worker   | `/`             | `python -m bot`                                         | none |

### Environment variables

The full runtime matrix lives in [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

Minimum website deployment set:

- `SITE_URL`
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`

Generate a `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Generate an `ADMIN_PASSWORD_HASH`:

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))"
```
