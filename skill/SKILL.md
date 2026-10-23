---
name: wine-cellar
description: Add or update owned wine bottles, review bottles awaiting an opening-year choice, or record opening and tasting feedback in the shared wine cellar. Use for cellar management; use wine-buying for store recommendations and wine-tonight-recommendation to choose a bottle.
---

# Wine Cellar

Use this skill to log purchases, maintain bottle records, and capture what a wine was like. Follow `AGENTS.md` in the repository or the installed reference at `references/AGENTS.md`.

Address the user as “Your Highness.” Keep routine phone interactions brief. The cellar is `cellar.jsonl`; the public read-only view is intended at <https://effectorgraph.github.io/wine-cellar/cellar-view.html>. A successful data save does not confirm that GitHub Actions rebuilt or published the view.

## Read and save

For a connected GitHub repository, use the GitHub MCP to fetch `EffectorGraph/wine-cellar` → `cellar.jsonl` on `main`, including its current SHA. Apply the confirmed edit to the complete JSONL and update the file with that SHA as the expected current version. If the SHA is rejected, fetch the latest content and SHA, then reapply only the confirmed user intent. Never force an overwrite. Local use may call the repository's scripts; use `update_wine.py` with `expected_sha256` for guarded edits.

After a successful source-data save, check the Actions result separately if available. Report whether data saved, and whether validation/build/publication completed. Do not say the view is updated or deployed until Actions confirms it.

## Bottle records

Use the current schema and preserve every field, including `bottle_id`, `status`, `verdict`, and `impressions`. Unknown facts and drink-window years may be null. Quick purchase capture can include only the known wine, vintage, and count; optional research can follow later. A new bottle needs a stable unique `bottle_id`.

Use `bottle_id` for updates. If absent, wine + vintage is a valid match only when exactly one row matches. If identity, vintage, or quantity is ambiguous, clarify that detail before changing data.

- `pending` and `cellared`: owned and unopened. `pending` means awaiting review, not awaiting purchase.
- `opened`: opening confirmed, tasting verdict still forming.
- `love`, `like`, `meh`, `pass`: consumed and rated.
- `finished`: consumed without a rating. Never invent a rating.

Recommendations do not establish purchase or consumption. Availability is recorded information, not a guarantee of live stock. Do not infer an opening from the recommendation, bottle age, or a store listing disappearing.

## Workflows

### Add a bottle

Capture only wines the user confirms they bought or already own. At a store, keep the exchange short and avoid delaying the log for missing details: record unknown vintage-specific facts and drink-window years as null. If the user wants research later, leave those fields for follow-up. Do not add recommended bottles they passed on.

### Review bottles

Review at most three explicitly requested bottles per catch-up. Show `pending` bottles in a concise list and ask for the target opening year (`cellared_under`); the user chooses it. Before changing status, check for an `opened_on` date. A `pending` or `cellared` row with an opening date has contradictory history: flag it and confirm what happened before changing status. Do not flip such a row to `cellared` just because a target year was supplied. Preserve all unrelated fields.

### Record an opening or finish

“We finished that” is sufficient to record consumption. Clarify only identity, vintage, or count if needed. Opening/consumption dates and verdict are optional. If the opening date is unknown, leave `opened_on` null; when adding an impression, use the date it was logged and make clear that the consumption date is unknown.

If no rating is given, use `finished`. Preserve prior ratings and history. If a user gives a new verdict, update `status`/`verdict` and append the new impression without deleting older impressions. When the user says a number of duplicate bottles were finished, use that explicit count: process bottles with the earliest `cellared_under` first, with null target years last. Keep unspecified quantity unknown.

For local guarded updates, `update_wine.py` accepts `expected_sha256`; finish requests use an explicit positive count, for example:

```json
{"action":"finish","match":{"wine":"Example Cabernet","vintage":2021},"count":1,"set":{"opened_on":null}}
```

If a remote save returns an uncertain result, reread `cellar.jsonl` and verify the target `bottle_id` values and desired fields before retrying. This prevents a repeated purchase append or finish action.

### Availability catch-up for tonight

When relevant to choosing a bottle, ask once which unopened bottle is available tonight. Do not turn this into a recurring schedule or require a mandatory availability checklist. Treat the answer as a useful snapshot, not certain inventory.

## Research and detail

For a full new entry or a requested bottle review, research producer technical sheets first, then named critics. Keep vintage-specific notes separate from cross-vintage or house-style context. Do not guess unknown values; use null. Match canonical winery names and existing conventions in the cellar.

Default to concise reports. Provide a detailed table only when requested. Never fabricate impressions or attribute the user's voice to critic tasting notes.
