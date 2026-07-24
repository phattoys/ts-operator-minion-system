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

### Execution Manifest Phase 3 — Intake/Transport

- **Status: IN DEVELOPMENT**

**Purpose:** Receive authenticated machine-readable campaign packets and
convert them into founder-reviewable Execution Manifests without
automatic execution.

**Architecture:**
```
TSAF creates.
Execution Manifest receives and structures.
OPS Execution Queue organizes.
OPS operators execute.
```

Adds two controlled intake paths: `POST /api/execution-manifest-intake/receive`
(authenticated server-to-server HMAC intake, for future TSAF delivery —
no live TSAF connection is claimed or configured) and
`POST /api/execution-manifest-intake/manual` (founder-session paste/upload
JSON, for testing/recovery/manual handoff). Both create manifests
exclusively through the existing, unmodified Phase 1
`create_manifest()`/`validate_manifest()` — no second manifest schema, no
duplicated validation or routing logic. Neither path queues a worker,
executes Jenny/Rene/WP Placement, issues a WP approval token, or writes
to WordPress or any connector — the founder still reviews and queues in
the existing Phase 2 workspace.

Frontend: `/execution-manifests/intake` — paste/upload JSON with a
local, readability-only preview, submit to the real manual-intake API,
see the resulting receipt (accepted/rejected/quarantined, errors,
warnings, link to the manifest), plus an Intake Receipts list/detail
view with status/source/transport filters.

See `docs/EXECUTION_MANIFEST_INTAKE.md` for the full inbound envelope,
HMAC signing process, checksum process, idempotency behavior, quarantine
rules, receipt model, asset-metadata boundary, ZIP/binary boundary
(explicitly future work, not built), and environment variables.

Not built in Phase 3 (explicitly out of scope, per instruction):
Metricool/Klaviyo/HubSpot/social publishing/vendor CSV/order-fulfillment
work, binary asset storage, ZIP extraction, media editing, CDN upload, a
live TSAF connection.

---

### OPS Practical Completion — Page Production

- **Status: BUILT** (pending real-environment/real-browser verification)

Following the OPS Practical Completion Audit (2026-07-22), one narrow
build closing the single defect the audit found: a `page_create`
execution item's own `copy`/`placement` fields now actually build the new
page — previously the create path silently required a pre-existing Page
Ops record and discarded the manifest's own content.

Three changes, all reusing existing infrastructure (no second WordPress
creation system, no worker redesign, no weakening of the write-safety
gate):

1. **Manifest-sourced page_create** — `services/worker_queue.py` gained
   `_execute_wp_create_from_manifest()`, used only when a task's context
   carries `manifest_page_data` (built by
   `services/execution_manifest.queue_execution_item()` for `page_create`
   items). Reuses the same templates, WordPress client, dry-run/approval
   flow, and placement logging as the original Page-Ops-sourced create
   path, which is otherwise completely unchanged and still handles every
   non-manifest caller exactly as before. Manifest `publication_mode` is
   still only ever an *intent* — it never itself authorizes a live write
   or a publish; the existing approval-token flow is untouched.
2. **Extended Rene WP content QA** — `_rene_qa_wp_content()` now checks,
   beyond the original presence/length/script-tag/target-ID basics:
   duplicate internal-link URLs and basic malformed-href detection
   (always on), plus CTA presence, minimum internal-link count,
   internal-only enforcement, required section markers, and SEO
   title/meta-description warnings — all opt-in per page via the manifest
   item's own `qa_requirements` (see `docs/EXECUTION_MANIFEST_SCHEMA.md`).
   No page is forced into another page's requirements.
3. **Maintainable internal-link map** — `services/menu_mapper.py`'s
   hardcoded link-suggestion tuples became a structured
   `INTERNAL_LINK_MAP` (source slug, destination slug, anchor label,
   reason, required/optional), plus a generic same-`page_family`/same-
   `district_or_pillar` fallback so new pages get real suggestions
   without needing to be pre-registered.

Not built (explicitly out of scope for this narrow completion, per
instruction): Feed MVP, any avatar work, connectors, vendor CSV, order
fulfillment, a broken-link crawler.

---

### WooCommerce Taxonomy Lane — Product Categories

- **Status: BUILT** (offline/mock-verified only — pending real-environment
  dry-run proof against live WordPress/WooCommerce and MongoDB; **do not
  mark known-good yet**)

**Purpose:** Let OPS read, dry-run, founder-approve, create, and update
WooCommerce product-category **taxonomy terms** through the Execution
Manifest lane, without misrouting them through the WordPress *page*
lane (`/wp/v2/pages`) they are not.

Smallest safe vertical slice, reusing existing infrastructure end to end
(no second write-safety system, no second approval-token engine, no
change to the page create/update lanes):

1. **Taxonomy REST client** — `services/wp_client.py` gained
   `get_product_category()`, `find_product_category_by_slug()`,
   `create_product_category()`, `update_product_category()`, targeting
   `/wp-json/wp/v2/product_cat` (the standard `wp/v2` route WooCommerce
   registers for this taxonomy — no separate `wc/v3` API needed for this
   site). Keyed by numeric `term_id`, never a `page_id`. Mock mode writes
   to `db.wp_mock_product_categories`, a collection entirely separate
   from `db.wp_mock_pages`.
2. **Object-type-bound approval tokens** — `services/wp_write_safety.py`
   gained an `object_type` parameter (default `"page"`, so existing page
   callers are byte-for-byte unaffected) threaded through
   `issue_approval_token`/`consume_approval_token`/`enforce_live_write`.
   A token issued for a page can never be consumed against a taxonomy
   write, or vice versa — same single-use, payload-hash-bound,
   scope-bound, expiring token engine as before, no second system.
3. **Routing** — `services/execution_manifest.determine_routing()` gained
   `taxonomy_update`/`taxonomy_create` → Rene (`wp_taxonomy_qa`) → WP
   Placement (`wp_taxonomy_update`/`wp_taxonomy_create`). Manifest
   content is authoritative; Jenny is skipped, matching the `page_create`
   precedent.
4. **Rene taxonomy QA** — `services/worker_queue._rene_qa_taxonomy_content()`
   reuses the same link-hygiene helpers as page QA (duplicate/malformed
   href, internal-only) plus taxonomy-specific checks: name/slug present,
   numeric `term_id` required for updates, duplicate-slug refusal for
   creates, and opt-in `intro_required` / `how_to_required` /
   `faq_count:N` / `cta_required` / `min_internal_links:N` /
   `internal_only` / `seo_required`.
5. **WP Placement taxonomy dry-run/live** —
   `_execute_wp_taxonomy_update()` / `_execute_wp_taxonomy_create()`
   default to `dry_run` exactly like the page lane: build the proposed
   description via a new `services/wp_placement.build_category_content()`
   (plain WYSIWYG HTML — WooCommerce term descriptions aren't Flatsome
   shortcode pages), show the exact `/wp-json/wp/v2/product_cat...`
   endpoint that would be called, and issue an object-type-bound token.
   Live/mock writes perform a read-after-write verification and log proof
   to a **new** `db.wp_taxonomy_placements` collection — `db.wp_placements`
   (page placement log) is untouched.
6. **Backlog schema** — `docs/backlogs/ts-14-category-taxonomy-backlog-20260723.json`,
   an executable Execution Manifest covering all 14 authoritative
   categories (13 `taxonomy_update` + 1 `taxonomy_create`). `copy` and
   `placement.description` are the literal placeholder
   `"PENDING_CONTENT — not yet drafted"` — verified to validate and route
   cleanly to `ready`/`needs_review` (correctly held at Rene QA pending
   real content, never silently waved through).

**Verified so far (offline, mock Mongo, no real WordPress/WooCommerce):**
`backend/tests/test_wp_taxonomy_lane.py` (32 tests) plus full existing
regression (132 tests: write-safety, worker-chain e2e, execution-manifest,
page-create-hardening, page-production-completion) — all green, zero
regressions. Confirms: taxonomy reads/writes use `/wp/v2/product_cat`
never `/wp/v2/pages`; `term_id` never crosses with `page_id`; dry-run
performs zero writes and issues a token; mock-mode write + read-after-write
verification is recorded; a page-object-type token cannot be replayed
against a taxonomy write and vice versa; tokens are single-use; live
writes are refused (loudly, not silently downgraded) in this
credential-less sandbox exactly like the page lane.

**Not verified (blocked in this sandbox, same boundary as every prior
phase — see the Phase 6 real-environment notes above):** behavior against
a real MongoDB, and behavior against real WordPress/WooCommerce
credentials. Do not run this lane's live-write path, and do not mark this
lane known-good, until that real-environment dry-run proof has been done.

Not built (explicitly out of scope for this narrow slice, per
instruction): a `wc/v3` fallback client (not needed for this site), a
dedicated HTTP route for direct (non-manifest) taxonomy placement (the
existing generic `/api/worker-queue/tasks/{id}/execute` endpoint already
works for taxonomy tasks with no route changes), automated
dependency-blocking execution ordering (the manifest's `dependencies`
field remains validated-for-existence/cycles only, same as before this
build — the one real ordering constraint in the 14-category backlog,
`strap-on-dildos` waiting on the new `lingerie-sets-babydolls-teddies`
category, is handled by simply omitting that link from
`related_links` until the dependency item is created, not by new
scheduling logic).

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
- The Execution Manifest Layer now exists in this repository (Phases 1-3:
  backend foundation, founder workspace, and intake/transport). It
  remains a receiving/structuring layer only — it does not build or
  modify TSAF, and no live TSAF connection is claimed or configured.

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
WP Placement's `task_types` were extended (not redefined) by the
WooCommerce Taxonomy Lane above to also include `wp_taxonomy_update` /
`wp_taxonomy_create` — its role and founder-gated/write-safety-gated
behavior are unchanged; it now acts on two distinct object types (pages
and WooCommerce category terms) via entirely separate code paths.

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
- **2026-07-16** — Execution Manifest Phase 3 (Intake/Transport) built:
  authenticated server-to-server HMAC intake (`/receive`) and
  founder-session manual intake (`/manual`), both creating manifests
  exclusively through the existing Phase 1 functions; SHA-256 checksum
  verification; mandatory idempotency (duplicate `idempotency_key` returns
  the original receipt; same `packet_id` with a different payload is
  quarantined as a conflict); quarantine/reject rules including inherited
  rejection of manifest `context.execution_mode`/`context.approval_token`
  via the existing Phase 1 validator; `execution_manifest_receipts`
  audit collection; receipt↔manifest traceability (backward compatible —
  no `receipt_id` required on legacy manifests); a founder-facing
  `/execution-manifests/intake` workspace (paste/upload JSON, local
  readability-only preview, submit, receipt result, Intake Receipts
  list/detail). No worker task is ever created and no WordPress write
  ever occurs as a result of intake. Status: IN DEVELOPMENT.
- **2026-07-22** — OPS Practical Completion Audit performed (read-only;
  no code changed). Identified one narrow defect blocking real website
  backlog work: manifest `page_create` items silently required a
  pre-existing Page Ops record and discarded their own content. One
  narrow completion build followed: manifest-sourced page creation
  (`_execute_wp_create_from_manifest`, reusing all existing
  templates/client/safety-gate/logging), extended Rene WP content QA
  (requirement-driven: CTA, internal-link count, internal-only,
  required sections, SEO warnings, plus always-on duplicate-link and
  malformed-href checks), and a maintainable `INTERNAL_LINK_MAP` in
  `services/menu_mapper.py` with a same-family/same-district
  auto-suggestion fallback for new pages. All KNOWN-GOOD components
  (write-safety gate, worker chain, Phases 1-3) preserved and re-verified
  by full regression. Branch `ops/page-production-completion-20260722`.
- **2026-07-23** — WooCommerce Taxonomy Lane built: the smallest safe
  vertical slice so OPS can read/dry-run/founder-approve/create/update
  WooCommerce product-category taxonomy terms without misrouting them
  through the WordPress page lane. Term-aware `wp_client.py` functions
  against `/wp/v2/product_cat`; `object_type`-bound approval tokens in the
  existing (unmodified in behavior) write-safety engine; new
  `taxonomy_update`/`taxonomy_create` routing to Rene (`wp_taxonomy_qa`) →
  WP Placement (`wp_taxonomy_update`/`wp_taxonomy_create`); a new,
  separate `db.wp_taxonomy_placements` proof log (page placement logging
  untouched); the authoritative 14-category backlog schema at
  `docs/backlogs/ts-14-category-taxonomy-backlog-20260723.json`. Page
  create/update lanes, Rene page QA, and all prior KNOWN-GOOD components
  preserved and re-verified by full regression (132 pre-existing + 32 new
  taxonomy tests, all green). Status: BUILT, offline/mock-verified only —
  **not marked known-good**; pending a real-environment dry-run proof
  against live WordPress/WooCommerce and MongoDB. Branch
  `ops/woocommerce-taxonomy-lane-20260723`, built on
  `ops/page-create-hardening-known-good-20260723` @
  `daebaf9bf4c1840f7334aa56d2fb47408cc01f5b`.
