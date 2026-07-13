# TS OPERATOR MINION SYSTEM Preservation Manifest

## Product Identity

This preserved baseline is for exactly one product:

**TS OPERATOR MINION SYSTEM**

Do not rename it, abbreviate it into another product, or infer that similarly named systems, branches, files, routes, workspaces, menus, or products belong to it.

This baseline is the standalone operational-hands system with the dark Founder Command Center interface.

## Source Artifact

- Artifact filename: `ts-operator-minion-system-known-good-20260712.zip`
- SHA-256: `7bde6e60e204b5c8d438cd0ce887929e2d0be4314297d71fe1acf2a3a3087f19`
- File count: `320`
- Original Emergent workspace path: `/app`
- Original branch: `main`
- Original workspace HEAD: `a42677ca49b8a4538f5d36c31c09f88da5334bad`
- Original export date: `2026-07-12`
- Original Git remote: none configured

## Preserved Paths

- Canonical archive:
  `/Users/chrystyle/Documents/TS Operator Minion System/archive/`
- Canonical ZIP:
  `/Users/chrystyle/Documents/TS Operator Minion System/archive/ts-operator-minion-system-known-good-20260712.zip`
- Canonical manifest:
  `/Users/chrystyle/Documents/TS Operator Minion System/archive/ts-operator-minion-system-known-good-20260712-manifest.txt`
- Frozen extracted baseline:
  `/Users/chrystyle/Documents/TS Operator Minion System/baselines/ts-operator-minion-system-known-good-20260712/`
- Dedicated local Git repository:
  `/Users/chrystyle/Documents/TS Operator Minion System/working/ts-operator-minion-system/`

## Known Visual Identity

The verified TS Operator Minion System baseline visibly includes:

- TS Operator login
- Page Ops Minion v1
- Founder Access
- Enter Ops Center
- Founder Command Center
- OPS
- Queue
- Page Queue
- Bulk Queue
- Exemplars
- Templates
- Styles
- Promotions
- Product Intake
- Field-to-Listing
- Catalog
- WP Placement

Known visual Founder Command Center state:

- 34 pages
- 14 review
- 19 live
- 0 planned
- 0 blocked
- 12 worker tasks needing review

## Proven Routes And Modules

Frontend routes are defined in `frontend/src/App.js`.

Core proven frontend files:

- `frontend/src/pages/Login.js`
- `frontend/src/pages/CommandCenter.js`
- `frontend/src/pages/WorkerQueue.js`
- `frontend/src/pages/PageQueue.js`
- `frontend/src/pages/BulkQueue.js`
- `frontend/src/pages/ExemplarLibrary.js`
- `frontend/src/pages/HouseTemplates.js`
- `frontend/src/pages/StyleProfiles.js`
- `frontend/src/pages/PromotionQueue.js`
- `frontend/src/pages/IntakeDashboard.js`
- `frontend/src/pages/FieldListingDashboard.js`
- `frontend/src/pages/CatalogDashboard.js`
- `frontend/src/pages/WpPlacementWorkspace.js`
- `frontend/src/components/Layout.js`

Core proven backend files:

- `backend/server.py`
- `backend/database.py`
- `backend/auth.py`
- `backend/routes/command_center.py`
- `backend/routes/worker_queue.py`
- `backend/routes/wp_placement.py`
- `backend/routes/page_ops.py`
- `backend/routes/product_intake.py`
- `backend/routes/field_listing.py`
- `backend/routes/catalog.py`
- `backend/services/worker_queue.py`
- `backend/services/command_center.py`
- `backend/services/wp_client.py`
- `backend/services/wp_placement.py`
- `backend/services/wp_formatter.py`

## Worker And Page-Update Baseline

Source-proven workers:

- Jenny
- Rene
- Sam
- WordPress Placement

Source-proven page-update workflow:

- `wp_content_draft`
- `wp_content_qa`
- `wp_page_update`
- `_route_next` DB re-fetch after Jenny completes
- `_execute_wp_update`

The `wp_placement` worker is configured with `auto_execute: false`, and queued WordPress work uses `founder_action_needed`.

## Known Unproven Items

These were not proven in the local preservation environment:

- Full backend runtime against the original Emergent MongoDB
- Original live database contents
- Re-running `backend/tests/test_page_update_workflow.py` without touching WordPress
- Full live WordPress execution
- Full rollback flow
- Full dry-run gate
- `dry_run_acknowledged`
- `operation_intent`
- `safety_gates`
- `human_approval_confirmed`
- `batch_approved`
- Later repair branch `ops-execution-wiring-fix-20260711`

## Credential And Secret Notes

The ZIP does not contain `.env` files, `node_modules`, or virtual environments.

The source includes `memory/test_credentials.md`, which documents the Founder test password and states the WordPress application password was stored in the excluded `/app/backend/.env`. Treat this repository as a preserved internal baseline, not as a public artifact.

## Preservation Rules

- The canonical archive is never edited directly.
- The frozen extracted baseline is never edited directly.
- All future development must happen on a single-purpose branch from the dedicated local repository.
- No upgrade may be ported without source identification, route/component mapping, safety review, tests, and visual verification where applicable.
- Do not merge unrelated products into this baseline.
- Do not infer product identity from names like minion, operator, queue, hub, grant, page, or worker.
- Do not touch WordPress or perform live writes unless explicitly authorized after dry-run and founder-approval checks are proven.
