# Website

This folder contains the Flask website for Open Mic Odyssey.

## Architecture

The website is a Flask application that uses a PostgreSQL database as its content store. The database schema is defined in `database/schema.sql`.

The application can be configured to use either the database or the JSON files in the `data/` directory as its content store by setting the `DATA_SOURCE` environment variable.

## Structure

- `app.py`: thin entrypoint that exposes the Flask application.
- `database/`: contains the PostgreSQL schema and migration plan.
- `data/`: JSON files containing structured content data for easy editing and maintenance.
- `movie_site/__init__.py`: app factory and Flask configuration wiring.
- `movie_site/admin.py`: admin UI dashboard and CRUD forms.
- `movie_site/auth.py`: Flask-Login user management and authentication.
- `movie_site/config.py`: Flask application configuration settings.
- `movie_site/content_store.py`: factory for getting the content reader/writer (JSON or DB).
- `movie_site/content_store_db.py`: database content reader/writer.
- `movie_site/db.py`: database connection pooling and helpers.
- `movie_site/views.py`: route handlers and page context assembly.
- `movie_site/movie_data.py`: assembles the page data model from the content store.
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

Current deployment is done to Coolify via nixpacks.

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

Movie content is stored in a PostgreSQL database. The admin dashboard at `/admin` provides a user interface for managing the content.

Alternatively, the application can be configured to use the JSON files in the `data/` directory as its content store by setting the `DATA_SOURCE` environment variable to `JSON`.

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
