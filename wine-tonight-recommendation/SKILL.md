---
name: wine-tonight-recommendation
description: Recommend an owned, unopened cellar bottle for tonight using the current cellar, recorded preferences, drinking readiness, and the user's occasion. Use when the user asks what to open or wants owned bottles compared. Keep the default answer concise; provide a detailed comparison table when requested.
---

# Wine Tonight Recommendation

Choose an owned bottle that fits tonight's goal and is ready to drink. Follow `AGENTS.md` in the repository or the installed reference at `references/AGENTS.md`.

Address the user as “Your Highness.” Lead with one clear recommendation and a short reason. A detailed table is optional and should be used when requested.

## Workflow

1. Fetch current `cellar.jsonl` and `preferences.json` from `EffectorGraph/wine-cellar` on `main` through GitHub MCP when available. For local use, pull the latest repository state before reading. Recommendations are read-only; never write merely because a bottle was suggested.
2. Consider only owned, unopened bottles with `status: pending` or `cellared` and no confirmed `opened_on` date. `love`, `like`, `meh`, `pass`, `finished`, and confirmed `opened` rows are not tonight's available options. Flag any `pending`/`cellared` row with an `opened_on` date as conflicting history; do not treat it as available without user confirmation. Do not infer availability from recommendation history, age, or a store listing.
3. When availability matters and is unknown, make at most one optional check about the recommended bottle. Treat the answer as a snapshot. Do not require a recurring schedule or a mandatory checklist.
4. Apply the requested scope literally. Region and appellation matter more than stylistic resemblance. For a “latest shopping trip” request, identify the relevant staging commit; do not infer it from nearby rows. Keep duplicate bottles as one option unless quantity changes the decision.
5. Compare the user's verdicts, impressions, and `preferences.json`. Explain the relevant taste fit and risk without flattening a nuanced preference into a generic ban.
6. Research only facts that could change the choice: vintage-specific composition or élevage, drinking window, maturity, or service. Use producer sources first, then named professional critics. Label house-style or cross-vintage context, and leave unavailable facts unverified. At home, current web research is allowed when useful.
7. Use the local store index for price context when available; label its recorded date and make clear that a shelf price does not establish what the user paid. Do not infer an owned bottle's availability from that index.

If the scoped set is empty, say so; do not widen it without asking. Keep the response compact by default. When a detailed comparison is requested, include rank, bottle, price if useful, verified composition/élevage, expected character, readiness, and service, with uncertainty named. Separate food pairing from the ranking unless the user makes it decisive.

When the user confirms opening a bottle, switch to `wine-cellar` to record it. “We finished that” is enough to record consumption; clarify only identity, vintage, or count if needed. A recommendation alone never changes bottle status.
