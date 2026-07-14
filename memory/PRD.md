# TS Operator Minion v1 - PRD

## Original Problem Statement
Build a lean internal operator system for Crystal's Temporary Satisfaction ecosystem. Reduce founder labor via modular minions for specific ops tasks.

## Architecture
- **Backend**: FastAPI + MongoDB | **Frontend**: React + Tailwind (dark terminal theme)
- **LLM**: GPT-5.2 (generation, listings, cost notes) + GPT-4o (Vision: PDF/photo analysis) + Claude Sonnet 4.5 (spec scoring) via Emergent LLM Key
- **Auth**: Single-founder password
- **WordPress**: Live REST API via Application Password
- **PDF Parsing**: pdfplumber + regex (SHEIN text), PyMuPDF + GPT-4o Vision (Temu image)
- **Image Storage**: Local `/app/backend/uploads/field_listing/` (cloud-swappable)

## App Structure (4-Layer Model)
| Layer | Route | Purpose |
|-------|-------|---------|
| **OPS** | `/` | Action dashboard — Today's Actions, Review, Launch, Blocked, Structure Map |
| **ECO Hub** | `/eco` | Ecosystem directory — Minion staffing chart, launcher, what each tool does |
| **Queue** | `/queue` | Cross-minion work queue — all tasks in motion with status filters |
| Module pages | `/page-queue`, `/field-listing`, `/wp-placement`, etc. | Individual minion workspaces |

## Active Modules (13)
1. Page Ops Minion — page generation, scoring, variants, promotions
2. Spec Writer Minion — software spec generation + scoring
3. Bulk Workflow Tools — batch processing for Page Ops
4. Lead Magnet Minion — downloadable lead magnets (PDF, 5 formats)
5. Product Intake Minion v3.2 — full intake-to-export pipeline, Vision PDF support
6. Operator Health Dashboard — cross-module founder visibility
7. Customer Comms Minion — brand-right communication drafting
8. Catalog Minion — normalize, dedupe, publish-readiness
9. WP Page Placement Minion v2.8.2 — structured content to WP drafts (LIVE)
10. **Field-to-Listing Layer v1** — PHOTO-FIRST batch intake → Vision AI analysis → listing records → marketplace packs
11. **Execution Spine v1** — orchestration layer connecting modules into one workflow system
12. **Worker Queue v1** — 4-worker task routing system (Jenny/Rene/Sam/WP) with auto-execution and founder safety
13. **Founder Command Center** — Today's actions, launch queue, blocking deps, page structure map, page codes

## Field-to-Listing Layer v1 — Photo-First UX
### Create Batch → Upload Photos → Add Notes → Analyze → Generate Listings → Generate Packs

**Photo-First UI Flow:**
- **Empty batch**: Large "Upload Product Photos" dropzone with "Drop phone photos, fixture pics, or product images here"
- **Batch notes below dropzone**: Source/Vendor, Grouped Pricing, Category/Type Hint, Condition/Pickup Note (all editable inline)
- **After upload**: Dropzone disappears, replaced by action bar with "Add More Photos", "Analyze Photos (N pending)", "Generate Listings", "Generate Packs"
- **Pricing bar**: Grouped pricing note with "Apply All" or "Apply (N selected)" button

**Multi-Photo Grouping:**
- Manual Merge: Select 2+ items → "Merge into 1 Item"
- Manual Split: Expand merged item → "Split into N items"
- Suggest Groups: Conservative auto-suggestion based on product type + color similarity
- Suggested groups banner with Accept/Dismiss per group

**Post-Merge Title Refinement (DONE - Feb 2026):**
- After merge, all images are sent to GPT-4o Vision with a title-specific prompt
- Extracts: color, pattern/print, cut/style, garment type from actual photos
- Generates listing-quality titles like "Red Cartoon Print Halter Bikini Set" instead of generic "Women's bikini"
- Standalone "Refine Title" button on any item with images (in expanded detail view)
- "REFINED" amber badge on titles that have been refined
- JSON parsing hardened with regex fallback for LLM response reliability

**Use cases:**
- In-store items never listed online
- Downtown LA / travel / opportunistic buys  
- Store fixtures / closeout / one-offs
- Phone photo batches
- Vendor-sourced items with no usable invoice

## Execution Spine v1 — Core Orchestration
### Signal Intake + Status Spine + Worker Routing + Execution Actions

**Normalized Statuses:** new → processing → needs_review → ready → exported/drafted/placed → done (+skipped, held_back)

**Routing Rules:**
- Page (ready) → "Place in WordPress" → WP Placement
- Intake Session (ready) → "Export WooCommerce CSV" → Product Intake
- Field Batch (ready) → "Generate Destination Packs" → Field-to-Listing

## Worker Queue v1 — Task Routing + Execution (DONE - Feb 2026)

**Workers:**
| Worker | Role | Auto-Execute | Tasks |
|--------|------|-------------|-------|
| Jenny | Listing Copy | YES | Title refinement, description gen, copy cleanup |
| Rene | QA / Cleanup | YES | Missing field checks, weak-title flagging, readiness |
| Sam | Routing / Packs | NO (founder-trigger) | Destination pack prep, marketplace routing |
| WP Placement | WordPress Actions | NO (founder-trigger) | WP draft creation, page placement |

**Routing Chain (hardcoded v1):**
1. Field-listing item analyzed → Jenny task (auto)
2. Jenny complete → Rene QA task (auto)
3. Rene QA passed → Sam destination-pack task (queued, founder-trigger)
4. Page approved in Page Ops → WP Placement task (queued, founder-trigger)

**WP Worker (WIRED - Feb 2026):**
- Fetches page from Page Ops → parses content → infers template → builds Flatsome HTML → creates real WP draft
- Updates page status to "placed" with wp_page_id and wp_placed_at
- Logs placement record in WP Placement log (source: worker_queue)
- Live on temporarysatisfaction.com — real drafts created (IDs 354779, 354780, etc.)

**Safety Rules:**
- Jenny/Rene stop + mark "Needs Founder Review" on: low confidence, missing critical fields, no usable images, generic titles
- No auto-publishing — Sam and WP always require founder click

**Queue Views:**
- Ready Now (founder-actionable), Needs Review, In Progress, Completed, Held Back

**Batch Execution:** Execute All Ready, Run Worker on selected items, Hold/Requeue individual tasks

**Activity Log:** Worker name, action, changes, success/fail, warnings, timestamps

## Founder Command Center (DONE - Feb 2026)

**Today's Actions** — tells Crystal exactly what to do:
- "4 pages ready for your review" (with page code chips like T3, S3, T1)
- "2 pages approved and ready to launch" (with Launch All button)
- "14 pages planned and ready to generate"
- "9 worker tasks waiting for your action"

**Page Code System:**
| Family | Code Prefix | Example |
|--------|-----------|---------|
| Core Hub | CH | CH1, CH2 |
| District | D | D1, D2, D3 |
| Trust | T | T1, T2 |
| FAQ/Support | S | S1, S2 |
| Guided Path | GP | GP1, GP2 |
| Conversion | C | C1, C2 |
| Category Support | CS | CS1, CS2 |
| Media/Asset | A | A1, A2 |
| Digital/Tools | DG | DG1 |

Auto-generated by family + sequence. Founder override available.

**Sections:** Today's Actions, Ready for Review, Ready to Launch, Blocked/Waiting, Structure Map (25 pages)

**Batch Operations:** Launch All approved pages, Generate planned pages

**Goal to Execution Map (DONE - Feb 2026):**
- Input: messy founder goal/brain dump + optional timeframe/priority/lane
- Output via GPT-5.2: Main Goal, Phases (3-6), First Actions (3-7), Dependencies, Minion Ownership, Crystal First Move
- Persisted to MongoDB as reusable operating assets
- "Send First Action to Queue" creates a real worker task
- Saved maps viewable and reloadable

**Minion Roles Directory:** Live stats for all 10+ modules with role, inputs, outputs, workflow stage

## Backlog
- P2: Session comparison view
- P2: Product Intake v3.3 (image upload, URL scraping)
- P2: ESP/email capture for Lead Magnets
- P2: Bulk WP draft creation from page lists
- P2: Quick Pack Preview for Field-to-Listing
- P2: Category-aware title refinement (different prompts for clothing vs. fixtures vs. jewelry)
- P3: Extract per-worker executors into services/workers/*.py modules for maintainability

## WP Write-Safety Gate Verification — 2026-07-14 (branch safety/unified-wp-write-gate-20260714)
- Verified HEAD eb52b32 (safety-gate source byte-identical); baseline 912cecd untouched; no merge, no new feature.
- Phases 1-7 all PASSED. Safety suites: 18/18 unit, 12/12 in-process HTTP, 9 pass/1 skip deployed.
- Phase 5 live draft: real WP page id 354948 created as DRAFT (not public, 404), single-use token consumed once, reuse rejected (409), payload byte-identical, approval identity server-derived.
- Full-suite 494 passed / 148 failed / 44 skipped / 27 errors — ALL failures are environment/data-dependency (empty DB, hardcoded IDs, LLM content) or intended dry_run-default contract change; ZERO safety-gate failures.
- FINAL STATUS: READY TO MARK KNOWN-GOOD. Did not begin Jenny->Rene->WP Placement E2E.
- Report: /app/VERIFICATION_REPORT_20260714.md
