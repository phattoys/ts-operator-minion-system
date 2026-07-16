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

### Execution Manifest Layer

- **Status: PHASE 1 IN DEVELOPMENT**
- **Source commit (Phase 1 backend foundation):** see change log below

**Purpose:** Bridge final structured campaign/output packets into safely
routed OPS execution work.

**Architecture:**
```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

Phase 1 delivers the smallest complete backend foundation: receive a
manifest, validate it, store it, show execution items and destination
instructions, convert approved executable items into existing OPS worker
tasks (reusing the Worker Queue rather than replacing it), and preserve
traceability from source packet → manifest → execution item → worker task
→ result/status.

Not built in Phase 1 (explicitly out of scope): external Metricool,
Klaviyo, HubSpot, email, or social API integrations; TSAF itself; order
fulfillment or vendor CSV functionality; any UI/dashboard.

This layer never calls the WordPress client directly and never issues or
consumes a WP approval token — it only ever creates ordinary
`worker_tasks` through the existing, unmodified Worker Queue, which routes
through the existing, unmodified Jenny → Rene → WP Placement chain and the
existing, unmodified WP write-safety gate. See
`docs/EXECUTION_MANIFEST_SCHEMA.md` for the full schema, destination
support table, and routing rules.

**Known remaining issue (pre-existing, not introduced or fixed here):**
`_execute_wp_update()` calls `int(wp_page_id)`, which can crash on
non-numeric mock WordPress page IDs. Not reached by the Phase 1 proof test
(which uses a realistic numeric WP page ID); tracked here as a standing
item, same as recorded under the worker-chain entry above.

---

### Execution Manifest Layer — Phase 1

- **Status: KNOWN-GOOD**
- **Verified source commit:** `7390c00edb0cfac2394fa10401221bfdd57afb66`
- **Real-environment verification date:** 2026-07-14
- **Verification manifest ID:** `man-verify-20260714`
- **Campaign name:** TS Execution Manifest Phase 1 Verification — 2026-07-14

**Verified facts:**
- Real MongoDB connectivity confirmed.
- Manifest persisted successfully in real database.
- Manifest could be fetched back by ID.
- Stored data matched submitted data.
- Manifest survived backend restart.
- WordPress execution item validated as ready.
- WordPress execution item routed deterministically to Jenny using wp_content_draft.
- Jenny task completed successfully.
- Rene task was auto-created and completed QA successfully.
- WP Placement task was auto-created.
- WP Placement remained queued.
- WP Placement did not auto-execute.
- WP Placement remained founder-gated.
- No real WordPress write occurred during this Phase 1 verification.
- Duplicate queue request did not create a duplicate Jenny task.
- Exactly one Jenny worker task existed for the execution item.
- worker_task_id was stored back on the manifest execution item.
- Metricool item remained visible and blocked.
- Metricool item did not create a fake worker task.
- Unsupported connector behavior was preserved honestly.
- Trace endpoint showed manifest → execution item → worker task → status → result → warnings.
- IDs aligned correctly across traceability chain.
- Forbidden manifest context fields execution_mode and approval_token were rejected.
- The Execution Manifest Layer could not bypass the existing WordPress write-safety gate.
- Real persistence remained intact after backend restart.
- 59 required regression tests passed.
- 1 legitimate conditional test was skipped.
- 0 required regression tests failed.
- Protected baseline remained untouched.

> **Protection rule:** DO NOT redesign, bypass, weaken, remove, or
> silently replace the KNOWN-GOOD Execution Manifest Phase 1 behavior
> without explicit architectural approval and a new verification cycle.

**Remaining known risks:**
1. `_execute_wp_update()` still calls `int(wp_page_id)`, which can fail on
   non-numeric mock WordPress page IDs. This is a pre-existing
   update-path issue and was not reached or repaired during Phase 1
   verification.
2. `mongomock-motor` and `pytest-asyncio` were installed locally for test
   execution but are not yet recorded in `requirements.txt`.
3. Verification data remains intentionally stored in the real database
   as labeled proof.

---

### Execution Manifest Layer Phase 2 — Founder Workspace

- **Status: KNOWN-GOOD**
- **Verified source commit:** `847bcc463090ee9acdc9006a89ac8e373969daf4`
- **Real-browser verification date:** 2026-07-15
- **Verification manifest:** `man-verify-phase2-browser-20260715`

**Verified facts:**
- Manifest list rendered successfully in the real browser.
- Manifest detail rendered successfully.
- WordPress execution item displayed correctly.
- Metricool execution item remained visible and blocked.
- Metricool showed FUTURE CONNECTOR PLANNED / connector unavailable behavior.
- Metricool had no fake worker task.
- Metricool showed no Queue button.
- Full trace displayed:
  Manifest → Execution Item → Jenny completed → Rene completed → WP Placement queued.
- Founder Action Center displayed the downstream queued WP Placement task.
- WP Placement showed founder_action_needed=true.
- WP Placement remained non-auto-executing.
- WP Placement next action preserved the dry-run preview and approval flow.
- No one-click live publish bypass existed.
- Metricool was excluded from Founder Action Center.
- Queue controls behaved honestly.
- No real WordPress write occurred.
- API and browser behavior matched.
- No application source files were modified during final verification.
- Protected baseline remained untouched.

> **Protection rule:** DO NOT redesign, bypass, weaken, remove, or
> silently replace the KNOWN-GOOD Execution Manifest Phase 2 founder
> workspace behavior without explicit architectural approval and a new
> real-browser verification cycle.

**Environment note:** the Emergent pod may start with gitignored `.env`
files absent and an empty MongoDB. For review-only verification data, use
the explicit, idempotent script:
```
python3 /app/scripts/seed_verify_manifest.py
```
Do not add automatic production startup seeding.

**Purpose:** Founder-facing review and execution workspace connected to
the known-good Phase 1 backend.

**Architecture:**
```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

Adds `/execution-manifests` (list + filters + sort + Founder Action
Center) and `/execution-manifests/:manifestId` (detail: header, execution
item cards, destination support badges, queue actions, trace, asset
index, honest empty/blocked/error states) to the OPS frontend. Calls the
existing, unmodified Phase 1 API only — no manifest validation, routing,
or write-safety logic is duplicated client-side; every decision displayed
comes from a backend response. See
`frontend/EXECUTION_MANIFEST_WORKSPACE.md` for routes, visible statuses,
queue behavior, founder-action behavior, unsupported-destination display,
and traceability display.

Not built in Phase 2 (explicitly out of scope, per instruction): Metricool/
Klaviyo/HubSpot/social connectors, order fulfillment, vendor CSV lane,
TSAF integration transport, a manifest/campaign-packet uploader beyond
what's needed to display existing manifests.

**Notable infrastructure fix (test tooling only, not application
behavior):** the frontend had zero existing tests and no
`@testing-library/*` packages. Adding them surfaced a pre-existing
incompatibility between `jest-resolve` v27 (bundled with `react-scripts`
5.0.1) and the conditional `"exports"` fields used by `react-router-dom`
v7 and current `axios` — both packages' `"main"` fallback points at a
file that doesn't match their real CJS entry point. Fixed via a
`moduleNameMapper` in `craco.config.js`'s new `jest` config block, plus a
`TextEncoder`/`TextDecoder` polyfill in `setupTests.js` that `jsdom`
(as bundled) doesn't provide but react-router v7 needs. This affects test
tooling only — production builds/webpack were already unaffected.

**Repair history:** an earlier real-browser review found the trace
API/UI showed only the initial Jenny task, and the Founder Action Center
never surfaced the downstream founder-gated WP Placement task. Root
cause and fix are recorded in the change log below (commit `847bcc4`).
WordPress safety (dry-run default, founder gating, approval token,
single/payload/scope binding, draft default, publish authorization) was
never touched, in the original build or the repair.

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
- **2026-07-14** — Execution Manifest Layer Phase 1 backend foundation
  built: data models, validation, deterministic routing, queueing into
  the existing Worker Queue, traceability, and API endpoints. Proven via
  automated tests, including the required in-process handoff: manifest →
  WordPress update item → Jenny task → Rene → WP Placement (remains
  founder-gated) → dry-run/approval/mock-write. Status: PHASE 1 IN
  DEVELOPMENT (backend only; no UI, no external connectors, no TSAF, no
  vendor CSV in this phase). Branch `ops/execution-manifest-phase-1-20260714`.
- **2026-07-14** — Execution Manifest Layer Phase 1 real-environment
  verified and marked KNOWN-GOOD. Commit
  `7390c00edb0cfac2394fa10401221bfdd57afb66`.
- **2026-07-14** — Execution Manifest Layer Phase 2 founder workspace
  built: manifest list (filters, sort, Founder Action Center), manifest
  detail (execution item cards, destination support badges, queue
  actions, trace view, asset index, honest empty/blocked/error states).
  Connected to the existing, unmodified Phase 1 API only. Status: IN
  DEVELOPMENT. Branch `ops/execution-manifest-phase-2-workspace-20260714`.
- **2026-07-14** — Repair pass on Phase 2: real-browser review found the
  trace API/UI showed only the initial Jenny task, and the Founder Action
  Center never surfaced the downstream founder-gated WP Placement task.
  Root cause: the execution item was only ever linked to the first task
  it created, never to the tasks the existing routing chain created
  afterward. Fixed by aggregating the full worker chain by
  `source_item_id` (ordered Jenny → Rene → Sam → WP Placement) in a new
  `get_worker_chain()` helper, exposed via `trace.worker_chain`, and used
  by both the detail view's trace section and the Founder Action Center.
  No worker-queue redesign, no WordPress-safety change. Status: REPAIR IN
  PROGRESS pending real-browser re-review.
- **2026-07-15** — Execution Manifest Layer Phase 2 repaired,
  real-browser verified, and marked KNOWN-GOOD. Commit
  `847bcc463090ee9acdc9006a89ac8e373969daf4`.
