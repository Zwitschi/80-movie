# Movie Project

This project contains materials and code for the "Open Mic Odyssey" movie project.

## Repository Structure

```text
README.md
website/
```

## Website

The public site is [openmicodyssey.com](https://www.openmicodyssey.com).

The web application lives in [website/README.md](website/README.md), which documents:

- the modular Flask app structure
- local development and deployment notes
- JSON-LD schema generation
- content, template, CSS, and background customization

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

## Static Export

Generate a deployable static bundle in `website/dist/` from the Flask app templates and data:

```powershell
f:\Documents\02-Projects\80-movie\.venv\Scripts\python.exe website\export_static.py
```

This command renders the public routes into HTML files, copies static assets into flat root-level directories under `website/dist/` such as `website/dist/css/`, `website/dist/images/`, `website/dist/js/`, and `website/dist/video/`, rewrites Flask-style asset and route links for static hosting, validates HTML structure, and validates JSON-LD blocks as JSON with a schema.org envelope check.

The repository keeps `website/generate_static_site.py` as the implementation module behind this command. `website/export_static.py` is the stable entrypoint for local use and CI.

The export also writes `website/dist/robots.txt` with crawler access enabled:

```text
User-agent: *
Allow: /
```

## Static Export Deployment

GitHub Actions can export and deploy the static bundle to the dedicated Pages repository.

Workflow:

- `.github/workflows/deploy-static-export.yml`
- triggers on push to `main` and on manual dispatch
- runs `python website/export_static.py`
- writes `build/robots.txt` as part of the generated bundle and allows crawlers by default
- stages the generated `website/dist/` contents into the destination repository folder `build/` in `WEBSITE_DEPLOY_REPOSITORY`
- pushes directly to `WEBSITE_DEPLOY_BRANCH` and defaults to `build` if the variable is unset

Required GitHub configuration in this source repository:

- Secret: `WEBSITE_DEPLOY_TOKEN`
  token with push permission to the destination Pages repository
- Variable: `WEBSITE_DEPLOY_REPOSITORY`
  destination repository in `owner/name` format, for example `Zwitschi/openmicodyssey-website`
- Optional variable: `WEBSITE_DEPLOY_BRANCH`
  destination branch; defaults to `build`

## Map Easter Egg

A hidden /map page displays a Mapbox GL JS route visualization of the film's road trip, built from TeslaCam GPS data.

### Access

The map is not listed in the site navigation. A hidden "Route Map" link in the footer becomes visible on hover.

### Configuration

The map requires a Mapbox public access token:

1. Create a free account at [mapbox.com](https://www.mapbox.com/) and copy your public token.
2. Add it to website/.env:
   ```
   MAPBOX_ACCESS_TOKEN=pk.your_token_here
   ```
3. For the static export deployment, add a MAPBOX_ACCESS_TOKEN secret to the GitHub repository.

### Route data

Route points are stored in website/static/data/map_data.json (649 GPS coordinates). The Mapbox GL JS logic lives in website/static/js/map.js.
