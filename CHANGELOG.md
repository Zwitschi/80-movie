# CHANGELOG

Compressed milestone log from `.github/instructions/DONE.md`.

## Website foundation

Restructured `website` into a modular Flask app, rebuilt shared layout and page flow, aligned templates with the static demo, added responsive trailer/video treatments, tightened metadata/JSON-LD/SEO, normalized naming and data ownership in `movie_data`, moved content into structured data sources, and refreshed README/docs around local run, deploy, schema, and content editing.

## Content, admin, and database

Built DB-backed content storage and migration flow, seeded main data into PostgreSQL, replaced old JSON/file management paths, added a full admin surface for film, media, content, events, FAQ, people, reviews, connect/social, and asset management, unified admin templates/CSS/auth, extracted shared helpers, and hardened content/editor workflows.

## Static export and deployment

Added static site generation with asset copy, HTML and JSON-LD validation, sitemap/robots generation, path-rewrite hardening, deploy-test coverage, GitHub Actions mirror/export flows, Heroku and Coolify deployment docs, PowerShell export helpers, and earlier OCI/Terraform planning before OCI-specific remnants were removed.

## Bot and control room

Delivered first embedded `/admin/bot` control-room phase, then extracted it into standalone `bot_api` surface with Discord OAuth operator auth, operator management, config/commands/syndication pages, PostgreSQL-backed config and syndication repositories, YouTube-first adapter + polling job + delivery sink, runtime health reporting, audit logging, shared website-content read contracts, queue and mileage domains, architecture/deploy updates, and post-extraction follow-through.

Historical ADRs for the embedded phase remain in `docs/adr/`, but active runtime ownership is now `control_room` for editorial CMS and `bot_api` for bot operator UI/API.

## Hardening and follow-through

Verified and applied missing DB migrations, made audit degradation non-blocking for control-room writes, fixed the mileage filter template, added runtime config fallback when managed bot config is unavailable, reran focused and full test suites cleanly, and updated the film cast section to dedupe people, merge roles, show descriptions when present, and hide the section when none exist.
