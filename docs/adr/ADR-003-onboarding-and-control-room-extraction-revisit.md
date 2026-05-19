# ADR-003: Onboarding Scope And Control-Room Extraction Revisit

- Status: Accepted
- Date: 2026-05-19

## Context

The worker, repository-backed config, audit log, queue domain, mileage domain, and embedded control-room slices now exist in the repository.

That was the explicit stability checkpoint for revisiting two deferred questions:

1. Should onboarding and role automation be implemented next inside the current boundaries or should that wait for a larger architecture shift?
2. Should the `/admin/bot` control room now be extracted into its own deployable surface?

The current codebase has clearer service and repository seams than it did when the embedded-first decision was made. It also now has a meaningful operator surface, explicit scopes, and multiple bot-owned domains. That makes the tradeoff easier to evaluate with real code instead of speculation.

## Decision

Keep the control room embedded for the next onboarding and role-automation phase.

Do not extract a separate control-room UI/API surface yet.

Implement onboarding and role automation as bot-owned domain logic behind service, repository, and command/event boundaries, with the embedded control room limited to configuration, inspection, and privileged operator overrides.

The near-term onboarding scope is:

- config-driven role assignment and revocation
- welcome and newcomer guidance hooks
- guild-specific onboarding state and policy
- operator-visible inspection, retry, and audit surfaces under `/admin/bot`

The near-term onboarding scope is not:

- a full standalone control-room frontend
- editorial-CMS-driven onboarding behavior
- merging operator auth with editorial admin auth
- Discord gateway logic inside Flask page handlers

## Rationale

- The code now has stable seams for bot-owned domains, but not yet a stable enough operator-product boundary to justify a second deployed frontend/API surface.
- Queue, mileage, syndication, and audit all still benefit from the low-friction embedded shell while operator workflows continue to settle.
- Extracting now would add packaging, deploy, auth, and internal API work before onboarding requirements are proven by real usage.
- The existing `/admin/bot/api/*` boundary and dedicated template namespace are sufficient to keep extraction possible later without forcing it now.

## Consequences

### Positive

- Onboarding work can start immediately on top of the existing bot domain structure.
- Role automation can reuse the current guild and role configuration model instead of waiting for a new UI shell.
- The current control room remains useful for operators without creating a second release train.

### Negative

- Website and control-room deployment remain coupled for one more phase.
- The embedded shell still carries some architectural pressure and must keep strict route and service boundaries.
- Onboarding UI polish should stay intentionally modest until workflow needs are clearer.

## Guardrails

- Keep onboarding behavior in bot command, event, service, and repository layers.
- Use the embedded control room for inspection, overrides, and config management only.
- Keep operator auth on Discord OAuth plus scoped `bot_operator` records.
- Prefer additive onboarding configuration tables or repository-owned state over ad hoc template or session logic.
- Preserve `/admin/bot/api/*` as the machine-readable contract that an extracted control room could later consume.

## Triggers To Revisit Extraction Again

Revisit control-room extraction when one or more of these become true:

- onboarding, moderation, or live-ops workflows need an independent release cadence
- operator UX needs richer realtime behavior than the embedded Flask shell reasonably supports
- non-Discord operator identities or service-to-service auth become a first-class requirement
- the website deployment blast radius becomes unacceptable for ops tooling changes
- internal bot/admin APIs become stable enough that a separate control-room surface reduces risk more than it adds

## Follow-On Work

- Implement onboarding and role automation as the next bot-owned domain slice rather than as Flask-first behavior.
- Reuse current config and audit conventions so onboarding actions stay inspectable.
- Keep extraction as a future deployment and boundary step, not a prerequisite for onboarding delivery.
