# Website

This folder contains the Flask website for Open Mic Odyssey.

## Structure

- `app.py`: thin entrypoint that exposes the Flask application.
- `movie_site/__init__.py`: app factory and Flask configuration wiring.
- `movie_site/views.py`: route handlers and page context assembly.
- `movie_site/movie_data.py`: editable movie content used by the page and schema graph.
- `movie_site/schema.py`: JSON-LD graph builder that renders Jinja schema templates and returns valid JSON.
- `templates/_base.html`: shared layout, stylesheet link, and JSON-LD script injection.
- `templates/index.html`: home page content that extends the base template.
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

The home page is served at `http://127.0.0.1:5000/`.

## Deployment Notes

The application object is exposed as `app` in `website.app`, so a WSGI-compatible deployment target can use:

```text
website.app:app
```

Examples:

- Heroku or other Procfile-based platforms: use a command such as `gunicorn website.app:app`.
- Platforms that support direct Flask or WSGI entrypoints: point them at `website.app:app`.
- If deploying behind a reverse proxy, keep static files under `website/static` available at `/static`.

If you add `gunicorn` or other deployment dependencies later, record them in your environment setup for the target platform.

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
- a detailed film page
- a credits page

Based on the stakeholder notes in the repository README, the next recommended phases are:

### Phase 1: Core release and discovery pages

- Trailer and watch page:
  centralize the trailer embed, teaser copy, and release-status messaging.
- Social and campaign links:
  add official outbound links for Instagram, TikTok, YouTube, crowdfunding, and Patreon in a dedicated, easy-to-scan section or page.
- Press and screening support:
  expand screening details, press-ready synopsis copy, and contact paths for festivals or media.

### Phase 2: Content-rich supporting pages

- Photo gallery page:
  for stills, posters, behind-the-scenes images, and promotional assets.
- Patreon or supporter page:
  explain membership content such as the main movie, Texas podcast material, driving footage, alternate edits, and bonus releases.
- Interactive stops map:
  if the trip structure is central to the documentary story, add a map page showing locations, dates, photos, and story beats.

### Phase 3: Optional experimental features

- Social embeds:
  pull curated Instagram, TikTok, and YouTube content into the site only if it improves the page rather than slowing it down.
- Web game or playful interactive piece:
  treat this as optional and only after the core release, trailer, credits, and supporter pages are stable.

### Recommended implementation order

1. Trailer/watch page
2. Social and crowdfunding links pass
3. Gallery page
4. Patreon/supporter page
5. Interactive map of stops
6. Experimental web game

### Approval gates

Before implementation, confirm these with stakeholders:

- whether crowdfunding is active and which platform is canonical
- whether Patreon content is approved and publicly describable
- whether map data, trip stops, and images are cleared for publication
- whether the web game is a real production goal or just a low-priority idea
