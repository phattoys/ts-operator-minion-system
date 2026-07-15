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

### Jenny → Rene → WP Placement Worker Chain

- **Status: KNOWN-GOOD**
- **Verified source commit:** `ee12901dcfb5759a0372b3e920adf19f42781e1e`
- **Live verification date:** 2026-07-14
- **Live verification page:** WordPress Page ID 354950
- **Exact title:** TS Operator Minion Worker Chain Verification — 2026-07-14

**Verified facts:**
- Jenny auto-executed and completed as implemented
- Rene was auto-created by routing, auto-executed, and completed QA
- WP Placement was auto-created by routing and did not auto-execute
- WP Placement remained founder-gated
- first manual execution reached needs_review
- dry-run returned preview, approval token, and expiry
- no live write occurred before approval
- exactly one real WordPress draft was created
- page 354950 remained draft after independent refetch
- unauthenticated public link, slug URL, and ?page_id=354950 all returned HTTP 404
- exact approved payload matched live WordPress raw content
- token was consumed exactly once
- second use of the same token was rejected
- second use caused zero additional writes
- exactly one real WordPress write occurred
- no unrelated WordPress content was modified
- all 9 pre-existing draft pages were preserved
- protected baseline remained untouched

> **Protection rule:** DO NOT redesign, bypass, weaken, remove, or
> silently replace the verified Jenny → Rene → WP Placement chain
> behavior without explicit architectural approval and a new
> end-to-end verification cycle.

**Known remaining issue (separate from the above — not reached or
repaired during this verification):** `_execute_wp_update()` currently
calls `int(wp_page_id)`, which can crash on non-numeric mock WordPress
page IDs. This is a pre-existing update-path bug, present in
`baseline/known-good-20260712`, unrelated to and not fixed by the
write-safety gate or worker-chain verification work.

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
- **2026-07-14** — Jenny → Rene → WP Placement worker chain proven
  end-to-end and marked KNOWN-GOOD using WordPress Page ID 354950.
  Commit `ee12901dcfb5759a0372b3e920adf19f42781e1e`.
