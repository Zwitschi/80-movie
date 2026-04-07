# Website

This folder contains the Flask website for Open Mic Odyssey.

## Structure

- `app.py`: thin entrypoint that exposes the Flask application.
- `movie_site/__init__.py`: app factory and Flask configuration wiring.
- `movie_site/views.py`: route handlers and page context assembly.
- `movie_site/movie_data.py`: editable movie content used by the page and schema graph.
- `movie_site/schema.py`: JSON-LD graph builder that renders Jinja schema templates and returns valid JSON.
- `templates/_base.html`: shared layout, stylesheet link, and JSON-LD script injection.
- `templates/overview.html`: overview page shown at `/`.
- `templates/index.html`: detailed film page shown at `/film`.
- `templates/gallery.html`: seeded photo gallery shown at `/gallery`.
- `templates/support.html`: broad public hub for social links, campaign updates, and lightweight support actions shown at `/support`.
- `templates/patreon.html`: supporter-membership page shown at `/patreon`.
- `templates/schema/*.json`: Jinja templates for schema.org nodes such as `Movie`, `Person`, `Organization`, `VideoObject`, `ScreeningEvent`, `Review`, `AggregateRating`, `Offer`, and `FAQPage`.
- `static/css/site.css`: shared site styles.
- `static/images/cinema-bg.svg`: full-page background art.

## Run Locally

From the repository root:

```powershell
f:\Documents\02-Projects\80-movie\.venv\Scripts\python.exe -m flask --app website.app run --debug
```

If the virtual environment is missing dependencies, install Flask first:

```powershell
f:\Documents\02-Projects\80-movie\.venv\Scripts\python.exe -m pip install Flask
```

Or install the tracked project dependencies from the repository root:

```powershell
f:\Documents\02-Projects\80-movie\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The main routes are:

- `/`: overview page
- `/watch`: compatibility redirect to the landing-page trailer section
- `/gallery`: stills, poster, and behind-the-scenes gallery
- `/support`: broad public hub for official channels, updates, and lightweight support actions
- `/patreon`: dedicated supporter-membership conversion page
- `/film`: detailed film page
- `/credits`: compatibility redirect to the credits section on `/film`

## Deployment Notes

The application object is exposed as `app` in `website.app`, so a WSGI-compatible deployment target can use:

```text
website.app:app
```

Examples:

- Heroku or other Procfile-based platforms: use a command such as `gunicorn website.app:app`.
- Platforms that support direct Flask or WSGI entrypoints: point them at `website.app:app`.
- If deploying behind a reverse proxy, keep static files under `website/static` available at `/static`.

## Gunicorn

`gunicorn` is now included in the tracked project dependencies in `requirements.txt`.

Typical production-style startup command from the repository root:

```text
gunicorn website.app:app --bind 0.0.0.0:8000
```

Recommended environment variables for deployment:

- `FLASK_ENV=production`
- `PYTHONUNBUFFERED=1`

Example Linux or WSL validation command:

```bash
source .venv/bin/activate
gunicorn website.app:app --bind 127.0.0.1:8000
```

Windows note:

- `gunicorn` installs successfully in the project environment, but it does not run natively on Windows because it depends on the Unix-only `fcntl` module.
- In this workspace, local gunicorn startup was attempted and failed for that expected platform reason.
- For local Windows development, continue using the Flask development server or run the gunicorn validation step inside WSL or another Linux environment before deploying.

## Mirror Deployment Workflow

The repository includes a GitHub Actions workflow at `.github/workflows/deploy-website-mirror.yml` that can publish the contents of `website/` into a separate repository.

What the workflow does:

- stages a clean deployment bundle from `website/`
- removes Python caches and common local artifacts
- copies `requirements.txt` into the mirrored repository root
- copies `website/README.md` to the mirrored repository root as `README.md`
- rewrites the mirrored README so the runtime entrypoint reflects the new repository root
- pushes the result to the target repository and branch you configure

Required GitHub configuration in the source repository:

- Secret: `WEBSITE_DEPLOY_TOKEN`
  a GitHub token with permission to push to the destination repository
- Variable: `WEBSITE_DEPLOY_REPOSITORY`
  the destination repository in `owner/repo` form
- Optional variable: `WEBSITE_DEPLOY_BRANCH`
  the destination branch name; defaults to `main` when omitted

Branch behavior:

- the workflow triggers on pushes to `main` that touch `website/**`, `requirements.txt`, or the workflow file itself
- it also supports manual execution through `workflow_dispatch`
- if the target branch does not exist yet, the workflow creates it
- if there are no content changes after staging, the workflow exits without creating a commit

Mirrored repository runtime note:

- in the mirrored repository, the former `website/` folder becomes the repository root
- because of that layout change, the mirrored app should run with `gunicorn app:app` rather than `gunicorn website.app:app`
- Flask development startup in the mirrored repository similarly becomes `python -m flask --app app run`

## Schema Generation

The structured data is generated in code, not hardcoded into the page.

Flow:

1. `movie_site/views.py` builds the page context.
2. `movie_site/schema.py` converts the movie data into a schema.org JSON-LD graph.
3. `render_schema_template()` renders the Jinja schema node templates from `templates/schema/`.
4. The graph is serialized to JSON and injected into `_base.html` inside a `<script type="application/ld+json">` block.

Current graph coverage includes:

- `Movie`
- `Person`
- `Organization`
- `VideoObject`
- `ScreeningEvent`
- `Review`
- `AggregateRating`
- `Offer`
- `FAQPage`

To add a new schema node type:

1. Add or update the supporting content in `movie_site/movie_data.py`.
2. Create a new Jinja template in `templates/schema/` if the type needs its own node shape.
3. Update `movie_site/schema.py` to render the new node and add it to the `@graph`.
4. Verify the resulting JSON-LD by loading the page locally and checking the generated script block.

## Updating Movie Content

Most content edits start in `movie_site/movie_data.py`.

Common updates:

- Title, tagline, synopsis, genre, runtime, and release messaging.
- Trailer URLs, thumbnail, duration, and upload date.
- Production company and contributor records.
- Screenings and ticket offers.
- Reviews, aggregate rating, and FAQ entries.

Guidelines:

- Keep user-facing page content and schema data consistent.
- Use real ISO dates and ISO 8601 durations where schema.org expects them.
- Leave fields as `None` rather than inserting placeholder values into date-specific schema properties.
- Prefer full absolute URLs for schema assets and canonical references.

## Template Customization

Use `templates/_base.html` for shared layout concerns:

- Document head elements
- Shared navigation and footer
- Global stylesheet link
- JSON-LD script injection

Use `templates/index.html` for page-specific content blocks.

If you add more pages later, extend `_base.html` rather than duplicating the shell.

## CSS And Background Customization

All shared styles live in `static/css/site.css`.

Recommended edit points:

- Update CSS variables in `:root` to change the palette.
- Adjust section, card, and hero styles in `site.css` rather than inline templates.
- Replace `static/images/cinema-bg.svg` if you want different background art.

Background behavior:

- Desktop uses a full-page image with `cover` sizing and a dark overlay.
- Mobile switches the background attachment behavior to `scroll` for better compatibility.

If you replace the background image, keep these constraints:

- Use a large asset that still looks good when cropped by `background-size: cover`.
- Preserve contrast so text remains readable against the hero and content sections.
- Prefer optimized SVG or compressed raster images to avoid unnecessary page weight.

## Planned Roadmap

The current site now has:

- an overview page
- a gallery page
- a support page
- a Patreon/supporter page
- a detailed film page
- credits folded into the film page, with `/credits` retained only as a compatibility redirect

Based on the stakeholder notes in the repository README, the next recommended phases are:

### Phase 1: Core release and discovery pages

- Trailer and landing page:
  centralize the trailer embed, teaser copy, and release-status messaging on the overview page and keep `/watch` only as a compatibility redirect.
- Social and campaign links:
  now centralized on the support page for Instagram, TikTok, YouTube, official site updates, and Patreon.
- Press and screening support:
  expand screening details, press-ready synopsis copy, and contact paths for festivals or media.

### Phase 2: Content-rich supporting pages

- Photo gallery page:
  now added as a dedicated page for seeded stills, posters, and behind-the-scenes assets that can be replaced with approved media later.
- Patreon or supporter page:
  now added as a dedicated page describing supporter access, bonus material, and a starter tier structure.
- Interactive stops map:
  if the trip structure is central to the documentary story, add a map page showing locations, dates, photos, and story beats.

### Phase 3: Optional experimental features

- Social embeds:
  pull curated Instagram, TikTok, and YouTube content into the site only if it improves the page rather than slowing it down.
- Web game or playful interactive piece:
  treat this as optional and only after the core release, trailer, credits, and supporter pages are stable.

### Recommended implementation order

1. Interactive map of stops
2. Experimental web game

### Approval gates

Before implementation, confirm these with stakeholders:

- whether crowdfunding is active and which platform is canonical
- whether Patreon content is approved and publicly describable
- whether map data, trip stops, and images are cleared for publication
- whether the web game is a real production goal or just a low-priority idea
