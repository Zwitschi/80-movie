# Movie Project

This project contains materials and code for the "Open Mic Odyssey" movie project.

## Repository Structure

```text
.github/           # GitHub-specific files (workflows, issue templates, etc.)
tests/             # Test suite for the project
website/           # Flask web application for the movie website
  database/        # PostgreSQL schema and migration plan
  static/          # Static assets (CSS, JS, images)
  templates/       # Jinja2 templates for rendering HTML pages
  movie_site/      # Flask app modules (views, models, admin, etc.)
  README.md        # Documentation for the website module
.gitignore         # Git ignore rules
pytest.ini         # Pytest configuration
README.md          # Root-level documentation for the overall project
requirements.txt   # Python dependencies for the project
run_tests.py       # Script to run the test suite
runtime.txt        # Python runtime specification for hosting environments
```

## Website

The public site is [openmicodyssey.com](https://www.openmicodyssey.com).

The web application lives in [website/README.md](website/README.md), which documents:

- the modular Flask app structure
- local development and deployment notes
- secure admin dashboard and content management
- JSON-LD schema generation
- content, template, CSS, and background customization

Environment variables for the website, embedded control room, and planned bot worker are documented in [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

Testing strategy for the website, control room, and bot scaffold is documented in [docs/TESTING.md](docs/TESTING.md).

Deployment guidance for the website, embedded control room, and planned split-service bot topology is documented in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

The website will include the following content:

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

Deploy the Flask app to Coolify using Nixpacks. Full steps are in [.github/instructions/DEPLOYMENT_COOLIFY.md](.github/instructions/DEPLOYMENT_COOLIFY.md).

For the broader split-service deployment view, including the embedded control room and planned bot worker, use [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Build settings

| Setting        | Value                                              |
| -------------- | -------------------------------------------------- |
| Build pack     | Nixpacks                                           |
| Base directory | `website` (this repo) or `/` (mirror repo)         |
| Start command  | `gunicorn app:app --bind 0.0.0.0:8000 --workers 2` |
| Port           | `8000`                                             |

### Environment variables

The full runtime matrix lives in [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

Minimum website deployment set:

- `SITE_URL`
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`

Common optional website values:

- `ADMIN_USERNAME`
- `MAPBOX_ACCESS_TOKEN`
- `CURRENT_YEAR`

If you enable the embedded control room or the future bot worker, use the Discord and bot-specific variables from [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) instead of extending this README with a second matrix.

Generate a `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Generate an `ADMIN_PASSWORD_HASH`:

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))"
```
