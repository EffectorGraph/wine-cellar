<!-- agent-sync:slot id="migration-001" audience="codex" -->
# Wine Cellar — shared agent guide
<!-- agent-sync:end -->

This is the canonical workflow guide for Codex and Claude. `CLAUDE.md` imports it. The repository stores cellar data in JSONL; the HTML cellar view is generated from that data. The four skills are `wine-cellar` (log, review, drink), `wine-buying` (shop), `wine-tonight-recommendation` (choose an owned bottle), and `wine-inventory-refresh` (refresh the store index).

## Safe cellar writes

- Prefer the connected GitHub MCP for reads and writes, especially on a phone. Fetch `EffectorGraph/wine-cellar` → `cellar.jsonl` from `main`, including its current SHA, before editing.
- Save the complete updated JSONL with that SHA as the expected current version. If the SHA conflicts, reread the latest file and reapply only the user's confirmed change. Never force or overwrite a conflict. If the connector is unavailable, use the local scripts with their SHA guard.
- If a save returns an uncertain result, reread the file and verify the intended bottle IDs and fields before retrying; do not append a duplicate purchase or finish bottles twice.
- Confirm the data save separately from the Actions rebuild/publication result. A successful save does not mean the generated view is rebuilt or published.
- Use stable `bottle_id` to update a physical bottle. If no ID is available, match by wine + vintage only when exactly one row matches; otherwise ask which bottle.
- Availability is recorded information, not certain live inventory. Never infer that a bottle was consumed from a recommendation, age, or a listing disappearing.

## Bottle lifecycle and logging

- `pending` and `cellared` mean owned and unopened. `opened` means opening is confirmed and a verdict is still forming. `love`, `like`, `meh`, and `pass` retain a tasting verdict. `finished` means consumed when no rating was given; do not invent one.
- A recorded bottle is available for a tonight recommendation only when its status is `pending` or `cellared` and `opened_on` is null. This is recorded availability, not confirmation that the bottle is physically on hand.
- “We finished that” is enough to record consumption. Clarify only bottle identity, vintage, or count when needed. Dates and a verdict are optional. If the opening date is unknown, leave `opened_on` null; an impression may use its logged date and say the consumption date is unknown.
- Preserve existing ratings, verdicts, and impression history. Add new impressions; do not replace prior notes. A new rating may update the verdict/status while retaining the history.
- Use only an explicitly stated quantity. When finishing some duplicate bottles, choose those with the earliest `cellared_under` first and null target years last; leave the remaining rows unchanged.
- Unknown vintage facts and drink windows can stay null and be researched later. Never block a quick purchase log on optional research.
- Recommendations are read-only. Record availability only when explicitly reported or verified; a recommendation is not evidence of opening or purchase.
- When a `pending` or `cellared` row has an `opened_on` date, flag the history conflict. Confirm what happened before changing its status; setting an opening-year target alone does not resolve it.
- Review at most three explicitly requested bottles in one catch-up. Do not turn review into a scheduled or mandatory checklist.

## Store sessions: keep them short

The user may be shopping on a phone with a hard token budget. No live web scraping or research and no subagent fan-out during live shopping. Do not make photo-by-photo uploads the primary path.

At the store, use the local inventory query script and the cellar/taste records. Query matches only; never load the raw inventory JSONL into context. If the index is missing or stale, say so and recommend from the cellar and general knowledge without live scraping. Refresh the index at home using `wine-inventory-refresh`.

Default to a concise phone-friendly recommendation. Give a detailed comparison table when asked. Keep questions to essential identification or purchase decisions.

## Inventory refresh

The Total Wine Centennial #2302 index is built at home. Read `inventory/SCHEMA.md` before changing `scan_store.py`; use `wine-inventory-refresh` for the scan workflow. Never run a refresh while the user is shopping in-store.

## Shared references

- The schema and local helper scripts live under `skill/scripts/`.
- The public read-only view is intended at <https://effectorgraph.github.io/wine-cellar/cellar-view.html>. Do not claim a change is deployed until publication is confirmed.
- Keep shared instructions free of personal names and machine-specific paths. Use the installed skill configuration to locate a clone.
