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

All services share a PostgreSQL database at `192.168.88.35` and run on Docker containers on a single Coolify deployment server instance behind Nginx Proxy Manager.

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

## Map Easter Egg

A hidden /map page displays a Mapbox GL JS route visualization of the film's road trip, built from TeslaCam GPS data.

### Access

The map is not listed in the site navigation. A hidden "Route Map" link in the footer becomes visible on hover.

### Configuration

The map requires a Mapbox public access token:

- Create a free account at [mapbox.com](https://www.mapbox.com/) and copy your public token.
- Add it to `website/.env` / Coolify environment variables as `MAPBOX_ACCESS_TOKEN`.

```dotenv
MAPBOX_ACCESS_TOKEN=pk.your_token_here
```

### Route data

Route points are stored in website/static/data/map_data.json (649 GPS coordinates). The Mapbox GL JS logic lives in website/static/js/map.js.

## Coolify Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full deployment steps. Quick reference:

| Service      | Base Dir        | Start Command                                     | Port |
| ------------ | --------------- | ------------------------------------------------- | ---- |
| Website      | `/` (repo root) | `waitress-serve --port 8880 website.app:app`      | 8880 |
| Control Room | `/` (repo root) | `waitress-serve --port 8480 control_room.app:app` | 8480 |
| Bot API      | `/` (repo root) | `waitress-serve --port 8787 bot_api.app:app`      | 8787 |
| Bot Worker   | `/`             | `python -m bot`                                   | none |

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
