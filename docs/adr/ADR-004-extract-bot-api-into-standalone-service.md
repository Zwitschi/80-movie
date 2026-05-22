# ADR-004: Extract Bot API Into Standalone Service

- Status: Accepted
- Date: 2026-05-22

## Context

ADR-001 established embedded-first control-room approach so bot operator workflows could ship before product and auth boundaries were fully stable.

ADR-003 then deferred extraction one more phase while queue, mileage, syndication, onboarding, audit, and operator workflows settled behind clearer service and repository seams.

That intermediate phase is now complete.

Current repository state includes:

- editorial CMS isolated in `control_room/` with `/`, `/login`, and `/content/*`
- bot operator UI and APIs isolated in `bot_api/` with `/bot/*` and `/bot/api/*`
- bot worker lifecycle remaining in `bot/`
- shared database and config seams already in place across all service surfaces

The embedded bot slice is no longer active runtime code. Keeping operator UI inside control-room boundary would now add confusion instead of reducing risk.

## Decision

Extract bot operator surface into standalone `bot_api` service.

`control_room` now owns editorial CMS only.

`bot_api` now owns:

- operator login via Discord OAuth
- operator HTML routes under `/bot/*`
- operator JSON APIs under `/bot/api/*`
- bot health, queue, mileage, onboarding, moderation, config, and syndication inspection and control flows

Worker execution remains outside browser-facing surfaces in `bot/`.

## Rationale

- Operator product boundary is now stable enough to justify separate deployment surface.
- Editorial CMS and bot operator workflows now have different auth, navigation, and release concerns.
- Existing shared DB, repository, and service seams made extraction incremental instead of rewrite.
- Standalone `bot_api` reduces ambiguity about which domain owns `/bot/*` behavior.

## Consequences

### Positive

- Editorial CMS and bot operator surface now have clear ownership boundaries.
- Deployment docs, health checks, and auth configuration can match actual runtime topology.
- Future operator-focused work can evolve in `bot_api/` without pretending to be CMS behavior.

### Negative

- Another deployed web surface must be configured and monitored.
- Historical docs, tests, and ADRs need explicit cleanup or superseded notes to avoid stale guidance.
- Cross-surface links must stay accurate, especially from control room into bot API.

## Guardrails

- Keep editorial workflows out of `bot_api/`.
- Keep bot operator workflows out of `control_room/`.
- Keep worker/runtime execution concerns in `bot/`, not in Flask route handlers.
- Preserve `/bot/api/*` as machine-readable contract for future frontend changes.
- Keep operator auth separate from editorial CMS auth.

## Follow-On Work

- Rename and maintain tests around `bot_api` ownership rather than embedded control-room naming.
- Mark earlier embedded-phase ADRs as superseded rather than rewriting their historical record.
- Keep architecture, deployment, and testing docs aligned whenever service boundaries change.
