# ADR-001: Embedded-First Control Room

- Status: Accepted
- Date: 2026-05-18

## Context

The repository already has a working Flask website, editorial CMS, PostgreSQL-backed content store, and a first embedded bot-operations slice under `/admin/bot`.

The broader control room is still evolving. Bot domains, permissions, and operator workflows are being defined, but operators already need a usable surface for health, login, and operator-management flows.

There are two realistic paths:

1. Build the first control-room experience inside the existing Flask app.
2. Stop and extract a separate UI/API surface before the operator workflows are fully known.

The architecture work already identified that immediate extraction would add deployment, API, and auth scaffolding before the product boundary is stable.

## Decision

Adopt an embedded-first control-room architecture.

The first operational control room will live inside the existing Flask app under `/admin/bot`, using a dedicated blueprint, template namespace, and operator session model.

This embedded slice must still behave like a separate application boundary:

- Keep operator routes under `/admin/bot` and operator APIs under `/admin/bot/api/*`.
- Keep bot-operations templates under `website/templates/admin/bot/`.
- Use operator auth that is separate from the editorial CMS login.
- Treat the Flask-hosted control room as a shell over service and repository boundaries, not as the owner of Discord gateway logic or broad bot business rules.
- Create a navigation section in the admin dashboard for links to bot operations.

Operator auth direction for the near-term and first extracted phase is also confirmed:

- Keep Discord OAuth as the operator authentication mechanism for control-room access.
- Keep authorization local through `bot_operator` records and explicit scopes.
- Do not merge control-room auth with the editorial CMS login model.
- Revisit only if the operator audience expands beyond Discord-identified staff or service-to-service access needs outgrow the current pattern.

## Rationale

- It delivers operator tooling with the lowest implementation and deployment overhead.
- It reuses the current website deployment while avoiding a premature second frontend and second backend surface.
- It keeps the route, auth, and template boundaries distinct enough that later extraction remains possible.
- It matches the current codebase, which already implements the first control-room routes inside the Flask application.

## Consequences

### Positive

- Operators get usable tooling sooner.
- The current website deployment can ship control-room improvements without standing up a separate service.
- Existing Flask session, template, and DB infrastructure can support the first phase.

### Negative

- Website and control-room releases remain coupled in the embedded phase.
- Process-level scaling stays shared with the public website.
- The team must actively protect boundaries so bot ops does not collapse into "more admin CMS".

## Guardrails

- Do not reuse the editorial admin session as operator identity.
- Do not put bot business logic directly in Flask page handlers.
- Do not let bot-operations templates and editorial templates drift into a single mixed namespace.
- Prefer service/repository seams and machine-readable ops APIs over template-driven operational logic.

## Triggers To Revisit

Revisit this ADR when one or more of these become true:

- The control room needs an independent deploy cadence.
- Live ops requires websocket-heavy or long-polling UX that fights the website shell.
- Permission complexity or audit requirements outgrow the embedded session model.
- Bot runtime and ops APIs become stable enough that a dedicated control-room surface reduces risk more than it adds.

## Follow-On Work

- Keep new control-room features inside the dedicated `admin_bot` slice.
- Preserve separate operator auth and scope enforcement.
- Treat later extraction as a deployment and boundary step, not as a reason to rewrite the domain model.
