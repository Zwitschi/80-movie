# Testing Strategy

This document is the source of truth for how tests are organized across the current website, embedded control room, and planned bot worker surfaces.

## Goals

- Keep the Flask website stable as the current production baseline.
- Catch regressions in the embedded `/admin/bot` control-room surface without having to run unrelated slices.
- Keep the bot scaffold testable as it grows from config parsing into a real worker.
- Make CI reflect the actual architecture by running separate slices for website, bot scaffold, and control room.

## Current test surfaces

| Surface      | Primary files                                                              | Purpose                                                                                |
| ------------ | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Website      | `tests/test_app.py`, `tests/test_schema.py`, `tests/test_content_store.py` | Public routes, admin auth/save path, schema output, and DB/pool behavior               |
| Control room | `tests/test_admin_bot.py`                                                  | `/admin/bot` auth, OAuth flow, session lifecycle, operator management, and health APIs |
| Bot scaffold | `tests/test_bot_scaffold.py`                                               | Bot config parsing and runtime bootstrap/shutdown behavior                             |

## Test layers

### Unit tests

Use unit tests when the behavior can be verified without Flask routing, real DB access, or external APIs.

Current examples:

- Bot config parsing in `tests/test_bot_scaffold.py`
- Scope normalization and permission checks when exercised through narrow control-room seams
- Small helper-driven save-path tests that stub the content reader/writer seam

Preferred characteristics:

- Fast execution
- No network
- No real database dependency
- Heavy use of `monkeypatch` or small fake objects when needed

### Contract tests

Use contract tests when the important behavior is the shape of data or responses between internal boundaries.

Current examples:

- Schema JSON-LD structure and required entity coverage in `tests/test_schema.py`
- Content payload shape and logical-file expectations in `tests/test_app.py`
- Control-room JSON API response structure in `tests/test_admin_bot.py`

Preferred characteristics:

- Assert on response or payload structure, not incidental formatting
- Protect shared assumptions between views, templates, content assembly, and future bot/control-room consumers

### Repository / integration tests

Use repository or integration tests when the behavior crosses app configuration, DB lifecycle, or content-store seams.

Current examples:

- DB-backed content reader coverage in `tests/test_app.py`
- App-scoped connection pool behavior in `tests/test_content_store.py`
- Flask app route tests that exercise real request handling and template rendering in `tests/test_app.py`

Current limitation:

- The repository mostly uses the live configured DB-backed content path rather than a dedicated ephemeral test database. Keep integration assertions focused on stable behavior and avoid overfitting to incidental data details.

### Smoke tests

Smoke tests answer: does the surface start and respond at all?

Current examples:

- Public page route checks in `tests/test_app.py`
- Bot runtime start/stop cycle in `tests/test_bot_scaffold.py`
- Control-room health and overview checks in `tests/test_admin_bot.py`

Use smoke tests to guard startup, route registration, and the most important happy paths. They should stay narrow and cheap.

## CI mapping

CI is intentionally split by architecture surface in `/.github/workflows/ci.yml`.

| CI job             | Command                                                                               | Scope                                                   |
| ------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Website tests      | `python -m pytest tests/test_app.py tests/test_schema.py tests/test_content_store.py` | Public site, admin auth/save path, schema, DB lifecycle |
| Bot scaffold tests | `python -m pytest tests/test_bot_scaffold.py`                                         | Bot config and runtime scaffold                         |
| Control-room tests | `python -m pytest tests/test_admin_bot.py`                                            | `/admin/bot` routes, auth, operator management          |

When adding new tests, keep them inside the slice that owns the behavior unless there is a strong reason to widen scope.

## Local execution

From the repository root:

```powershell
python -m pytest
```

Run the same slices as CI:

```powershell
python -m pytest tests/test_app.py tests/test_schema.py tests/test_content_store.py
python -m pytest tests/test_bot_scaffold.py
python -m pytest tests/test_admin_bot.py
```

The convenience runner in `run_tests.py` still supports a few historical selectors, but direct `pytest` commands are the preferred path because they match CI exactly.

## Authoring guidance

### Website

- Prefer request-level tests in `tests/test_app.py` for public routes and admin auth flows.
- Add schema assertions in `tests/test_schema.py` when changing JSON-LD graph structure.
- Add DB lifecycle or pool behavior checks in `tests/test_content_store.py` when touching `db.py` or content-store plumbing.
- For admin save paths, stub the content reader/writer seam instead of mocking unrelated Flask internals.

### Control room

- Keep `/admin/bot` behavior in `tests/test_admin_bot.py`.
- Verify both page and API behavior when auth, scope, or operator-management logic changes.
- Prefer session-based setup through `client.session_transaction()` over bypassing the control-room auth flow globally.

### Bot scaffold

- Keep config parsing, runtime lifecycle, and early orchestration tests in `tests/test_bot_scaffold.py` until the bot grows enough to justify dedicated service or repository test files.
- Add narrow unit tests first for new bot services, then add one smoke-style runtime test if registration or startup behavior changes.

## What to add next

- Dedicated tests for additional admin CRUD domains beyond the current representative film save path
- Bot service-level tests once the scaffold grows real repositories, commands, or jobs
- More repository-focused coverage around bot operator persistence and future bot-owned tables
- Deploy-time smoke checks once split-service deployment docs and scripts exist
