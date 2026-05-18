# ADR-002: Shared Data Ownership And Integration Strategy

- Status: Accepted
- Date: 2026-05-18

## Context

The website, planned bot worker, and control room need to share some production and operational data, but they do not have the same responsibilities.

The current website already owns editorial content and publishes public pages from PostgreSQL-backed data. The planned bot worker will need its own operational state for queues, mileage, syndication, and audits. The control room needs cross-surface visibility without becoming the write owner of everything.

The main design risk is cross-surface write sprawl: once multiple runtimes write the same tables directly, deploys, migrations, and incident recovery become fragile.

## Decision

Use a shared PostgreSQL instance with explicit single-writer ownership per table, read-first cross-surface access, and a minimal shared contract layer.

The strategy is:

- Website-owned editorial tables remain writable only by the website and editorial CMS.
- Bot-owned operational tables remain writable only by the bot service.
- Shared read models and integration tables may exist, but each still has one clear write owner.
- Cross-surface reads are allowed.
- Cross-surface writes are not allowed without going through the owning surface's boundary or an owner-controlled integration table.
- Start with direct DB contracts for stable read scenarios and add internal APIs only when direct shared-table reads become unsafe or too coupled.

## Rationale

- The repo already uses PostgreSQL as the shared persistence baseline.
- Single-writer ownership keeps deploys and migrations safer across independently evolving surfaces.
- Read-first sharing is enough for the near-term website, embedded control room, and bot-planning use cases.
- Deferring internal APIs avoids inventing network boundaries before the consumers and payloads are stable.

## Ownership Rules

- Each table has exactly one write owner.
- Website rendering must not depend on bot-owned tables for correctness.
- Bot-owned tables should use visible prefixes such as `bot_`.
- Shared read models should be append-only or rebuildable where possible.
- Avoid foreign keys from website-owned tables into bot-owned tables.

## Shared Contract Rules

- Keep the first shared contract intentionally small and read-only.
- Prefer DTO-style read models such as production metadata, screening summaries, and campaign link summaries.
- Make shared changes additive first.
- Treat breaking schema or DTO changes as coordinated compatibility work, not casual refactors.

## Consequences

### Positive

- The website can remain the source of truth for public editorial content.
- The bot can evolve operational persistence without taking ownership of website content.
- The control room can read across surfaces without forcing early API infrastructure.
- Migrations can be planned with compatibility windows instead of same-minute rollouts.

### Negative

- Shared-database access still requires discipline to avoid accidental write creep.
- Some future integrations may need API boundaries later, which means this is not the last architectural step.
- The team must document ownership clearly in migrations, repositories, and operational docs.

## When To Introduce Internal APIs

Add internal service APIs when one or more of these apply:

- Direct DB reads expose unstable or overly coupled table shapes.
- Authorization rules depend on service-owned policies rather than simple read access.
- A surface needs mutations in another surface's owned data.
- Operational isolation or deployment independence becomes more important than direct shared-schema convenience.

## Follow-On Work

- Keep migration files and repository code explicit about table ownership.
- Preserve compatibility windows in shared-database changes.
- Use rebuildable integration tables or projections where cross-surface state needs denormalized views.
- Revisit the direct-DB-versus-internal-API threshold as bot domains become concrete.
