# TS OPERATOR MINION SYSTEM Upgrade Ledger

## Baseline Status

- Baseline: frozen
- Artifact: `ts-operator-minion-system-known-good-20260712.zip`
- Baseline HEAD reference: `a42677ca49b8a4538f5d36c31c09f88da5334bad`
- Local baseline branch: `baseline/known-good-20260712`
- Baseline tag: `baseline-known-good-20260712-a42677c`

## Current Upgrade State

No upgrades have been ported.

No repair branch code has been copied.

No WordPress write has been performed.

No remote has been added.

## Later Repair Source

The later repair source `ops-execution-wiring-fix-20260711` was unavailable during preservation. Its expected HEAD was:

`0e0959039ecad300354269f640c54671ead649df`

Until that exact source is provided and verified, all later repair work remains `CANNOT PROVE`.

## Future Upgrade Rules

Every future upgrade must be:

- single-purpose
- source-identified
- mapped from exact source files to exact destination files
- reviewed for unrelated product contamination
- implemented on its own branch
- tested independently
- visually verified when frontend behavior changes
- blocked from live WordPress writes unless explicitly authorized

## Initial Candidate Ledger

| Upgrade | Status | Recommendation |
|---|---|---|
| Page inventory/sync | Not ported | Needs more investigation |
| Page identity correctness | Not ported | Needs more investigation |
| Dry-run acknowledgement wiring | Not ported | Needs more investigation |
| Queue visibility | Not ported | Needs more investigation |
| Jenny to Rene to WP Placement proof | Not ported | Port later |
| Founder approval proof | Not ported | Port later |
| Controlled live WordPress proof | Not ported | Port later |
| Verification and rollback | Not ported | Needs more investigation |
