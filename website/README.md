# Website

This folder contains the Flask website for Open Mic Odyssey.

## Structure

- `app.py`: thin entrypoint that exposes the Flask application.
- `data/`: JSON files containing structured content data for easy editing and maintenance.
  - `movies.json`: core movie metadata and content.
  - `people.json`: cast and crew information.
  - `organizations.json`: production companies and organizations.
  - `media_assets.json`: images, videos, and media resources.
  - `events.json`: screening events and showings.
  - `reviews.json`: critical reviews and ratings.
  - `offers.json`: distribution and viewing options.
  - `faq.json`: frequently asked questions.
  - `gallery.json`: photo gallery content.
  - `social.json`: social media links.
  - `connect.json`: campaign and supporter information.
  - `content.json`: page-level SEO metadata (titles, descriptions, keywords, paths) and per-page static content (headings, body copy, bullet lists, CTA card data) exposed to templates via `page_content`.
- `movie_site/__init__.py`: app factory and Flask configuration wiring.
- `movie_site/admin.py`: admin UI dashboard and CRUD forms.
- `movie_site/auth.py`: Flask-Login user management and authentication.
- `movie_site/config.py`: Flask application configuration settings.
- `movie_site/content_store.py`: secure JSON file read/write operations for admin features.
- `movie_site/views.py`: route handlers and page context assembly.
- `movie_site/movie_data.py`: JSON loader that assembles the page data model from `data/*.json`.
- `movie_site/schema.py`: JSON-LD graph builder that renders Jinja schema templates and returns valid JSON.
- `movie_site/schema_parts/`: modular schema generation components.
  - `__init__.py`: schema utilities and helpers.
  - `events.py`: screening event schema generation.
  - `graph.py`: main schema graph building logic.
  - `media.py`: media asset schema generation.
  - `movie.py`: movie entity schema generation.
  - `offers.py`: offer schema generation.
  - `organization.py`: organization schema generation.
  - `people.py`: person schema generation.
  - `reviews.py`: review schema generation.
  - `social.py`: social media schema generation.
- `templates/_base.html`: shared layout, stylesheet link, and JSON-LD script injection.
- `templates/index.html`: overview page shown at `/`.
- `templates/film.html`: detailed film page shown at `/film`.
- `templates/media.html`: seeded media page shown at `/media`.
- `templates/connect.html`: broad public hub for social links, campaign updates, and lightweight support actions shown at `/connect`.
- `templates/patreon.html`: supporter-membership page shown at `/patreon`.
- `templates/admin/`: CRUD form templates for managing site data.
- `templates/schema/*.json`: Jinja templates for schema.org nodes such as `Movie`, `Person`, `Organization`, `VideoObject`, `ScreeningEvent`, `Review`, `AggregateRating`, `Offer`, and `FAQPage`.
- `static/css/site.css`: shared site styles.
- `static/js/scripts.js`: client-side JavaScript functionality.
- `static/images/`: image assets including background art and media files.
- `static/video/`: video assets and media files.

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
- `/media`: stills, poster, and behind-the-scenes media page
- `/connect`: broad public hub for official channels, updates, and lightweight support actions
- `/patreon`: dedicated supporter-membership conversion page
- `/film`: detailed film page
- `/credits`: compatibility redirect to the credits section on `/film`
- `/admin`: secure content management dashboard (requires login)

## Deployment

Current deployment workflows documented in this repository:

1. GitHub Actions mirror workflow for publishing `website/` content to `zwitschi/openmicodyssey-website`.
2. Static export workflow for generating and publishing `website/dist/`.

See the root `README.md` for static site export and GitHub deployment instructions.

## GitHub Mirror Workflow

This repository includes `.github/workflows/deploy-website-mirror.yml` to publish only website content.

What the workflow does:

- stages a clean bundle from `website/` only
- removes caches and local artifacts
- copies `requirements.txt` into the mirrored repository root
- copies `website/README.md` into the mirrored repository root as `README.md`
- rewrites entrypoint references from `website.app:app` to `app:app`
- pushes changes to `https://github.com/zwitschi/openmicodyssey-website`

Required GitHub configuration in this source repository:

- Secret: `WEBSITE_DEPLOY_TOKEN`
  token with push permission to `zwitschi/openmicodyssey-website`
- Optional variable: `WEBSITE_DEPLOY_BRANCH`
  destination branch; defaults to `main`

Trigger behavior:

- runs on pushes to `main` when `website/**`, `requirements.txt`, or workflow files change
- supports manual run via `workflow_dispatch`
- skips commit if staged content matches destination branch

Runtime entrypoint in mirrored repository:

- `gunicorn app:app --bind 0.0.0.0:8000`

## Schema Generation

The structured data is generated in code, not hardcoded into the page.

Flow:

1. `movie_site/movie_data.py` loads content data from JSON files in the `data/` folder.
2. `movie_site/views.py` builds the page context using the loaded data.
3. `movie_site/schema_parts/graph.py` converts the movie data into a schema.org JSON-LD graph.
4. Schema generation modules in `movie_site/schema_parts/` render individual node types using Jinja templates from `templates/schema/`.
5. The graph is serialized to JSON and injected into `_base.html` inside a `<script type="application/ld+json">` block.

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

1. Add or update the supporting content in the appropriate JSON file within the `data/` folder.
2. Create a new Jinja template in `templates/schema/` if the type needs its own node shape.
3. Add schema generation logic to the appropriate module in `movie_site/schema_parts/`.
4. Update `movie_site/schema_parts/graph.py` to include the new node in the main graph.
5. Verify the resulting JSON-LD by loading the page locally and checking the generated script block.

## Updating Movie Content

Most content edits now start in the JSON files within the `data/` folder for easy editing without touching Python code.

Common updates:

- `movies.json`: Title, tagline, synopsis, genre, runtime, and release messaging.
- `media_assets.json`: Trailer URLs, thumbnail, duration, and upload date.
- `organizations.json`: Production company information.
- `people.json`: Contributor and cast records.
- `events.json`: Screenings and ticket offers.
- `reviews.json`: Reviews, aggregate rating.
- `faq.json`: FAQ entries.
- `gallery.json`: Photo gallery content.
- `social.json`: Social media links.
- `connect.json`: Campaign and supporter information.
- `content.json`: Page-level SEO metadata (titles, descriptions, keywords, paths) and per-page static content (headings, body copy, bullet lists, CTA card data).

Guidelines:

- Keep user-facing page content and schema data consistent.
- Use real ISO dates and ISO 8601 durations where schema.org expects them.
- Leave fields as `None` rather than inserting placeholder values into date-specific schema properties.
- Prefer full absolute URLs for schema assets and canonical references.
- Edit `data/content.json` to update page-level SEO titles, descriptions, and keywords, or to change page body copy, headings, bullet lists, and CTA card text, without touching Python code or HTML templates. Each page entry has a `content` object whose keys map directly to `{{ page_content.* }}` variables in the corresponding template.

## Template Customization

Use `templates/_base.html` for shared layout concerns:

- Document head elements
- Shared navigation and footer
- Global stylesheet link
- JSON-LD script injection

Use `templates/film.html` for page-specific content blocks.

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
- a media page
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

- Media page:
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
