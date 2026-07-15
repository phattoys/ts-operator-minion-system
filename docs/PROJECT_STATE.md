# TS Operator Minion System — Canonical Project State

This file is the single shared source of truth for project status,
component readiness, and naming, so Claude, ChatGPT, Codex, and future
builders can work from the same facts without Crystal manually passing
notes between everyone. Update it, don't fork it.

---

## Project Naming (authoritative)

- **Minion Hub = ECO-Minion** — a separate project.
- **Temporary Satisfaction Operator Minion System = TS Operator Minion / OPS** — this repository.
- These are **separate projects**. Do not conflate them.
- There is **no third project called "TS Minion."**
- Also distinct from **TSAF (TS Ad Foundry)** — see Handoff Architecture below.

---

## Component Status

### Unified WordPress Write-Safety Gate

- **Status: KNOWN-GOOD**
- **Verified source commit:** `eb52b3200aa7309fc29ef53e4ce6cb448163f02d`
- **Live verification date:** 2026-07-14
- **Live verification page:** WordPress Page ID 354949

**Verified facts:**
- mock mode never touches live WordPress
- dry_run is default
- dry_run returns preview and approval token
- token is payload-hash-bound
- token is scope-bound
- token is single-use
- token TTL is configurable, default 60 minutes
- approval identity is server-derived
- live write requires approval token
- live write defaults to draft
- publish requires explicit authorization
- exactly one real WordPress draft was created
- page 354949 remained draft
- public URL returned HTTP 404
- exact approved payload matched live WordPress content
- second token reuse returned HTTP 409
- no unrelated WordPress content was modified
- protected baseline remained untouched

> **Protection rule:** DO NOT redesign, bypass, weaken, remove, or
> silently replace the Unified WordPress Write Safety Gate without
> explicit architectural approval and a new verification cycle.

Implementation: `services/wp_client.py` (authoritative enforcement),
`services/wp_write_safety.py` (token issuance/consumption),
`routes/wp_placement.py`, `services/worker_queue.py` (wp_placement
worker), `models.py` (`WpExecutionMode`, `WpPublicationMode`,
`WpWriteApproval`, `WpApprovalRecord`).

---

## OPS Handoff Architecture

```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

- TSAF is separate from OPS.
- OPS girls do not directly touch TSAF.
- TSAF currently only has product/category visibility from the website.
- The Execution Manifest Layer does not exist in this repository yet
  (confirmed by repository audit — no code, no models, no stub). It is
  planned, not implemented.

---

## Workers Verified In Code

Exactly four, defined in `WORKERS` in `services/worker_queue.py`:

| Worker | Role | Auto-execute |
|---|---|---|
| Jenny | Listing Copy / WP Content Drafting | Yes |
| Rene | QA / Cleanup / WP Content QA | Yes |
| Sam | Routing / Destination Packs | No (founder-triggered) |
| WP Placement | WordPress Action Worker | No (founder-triggered, write-safety gated) |

Do not invent responsibilities beyond what is present in code. This
table reflects `services/worker_queue.py` as of `eb52b3200aa7309fc29ef53e4ce6cb448163f02d`.

---

## Change Log

- **2026-07-12** — `baseline/known-good-20260712` established (see
  `PRESERVATION_MANIFEST.md`).
- **2026-07-14** — Unified WordPress Write-Safety Gate designed,
  implemented, unit- and HTTP-level verified, one repair applied
  (publish-authorization status derivation), and live-verified against
  real WordPress (Page ID 354949). Marked KNOWN-GOOD. Commit
  `eb52b3200aa7309fc29ef53e4ce6cb448163f02d`.
