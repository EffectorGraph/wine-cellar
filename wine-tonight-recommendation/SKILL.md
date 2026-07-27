---
name: wine-tonight-recommendation
description: Use this skill whenever Andrew asks what wine to open or drink tonight, wants owned cellar bottles compared or ranked for an occasion, meal, mood, region, grape, producer, or recent shopping trip, or asks for the detailed recommendation table with price, composition, character, readiness, and service guidance. Pull the shared cellar first, identify only owned unopened bottles within the literal requested scope, research missing vintage-specific facts and current price context, rank against the recorded taste profile and drinking windows, and keep food pairing separate unless the user makes it decisive. Do not use for shopping, adding bottles, setting cellar years, or recording tasting feedback.
---

# Wine Tonight Recommendation

Recommend which owned bottle to open now. Ground the call in the current cellar, Andrew's recorded taste, vintage-specific research, maturity, and opportunity cost. Produce the exact rich table defined below.

Address Andrew as "Your Highness". Be concise but substantive.

## Workflow

### 1. Sync before reading

Find the wine-cellar repository:

1. Use the current workspace if it contains `cellar.jsonl` and `preferences.json`.
2. Otherwise read the configured `repo_path` from the installed `wine-cellar` skill (`~/.agents/skills/wine-cellar/.local-config.json` or `~/.claude/skills/wine-cellar/.local-config.json`).
3. Personal fallback: `/Users/andrew/repos/databases/wine-cellar`.

Run `git pull --ff-only` before identifying options. Preserve unrelated local changes; never discard them to make the pull work. If a dirty file blocks the pull, preserve only that file non-destructively, pull, then restore it.

### 2. Resolve the literal scope

Read `cellar.jsonl`. Unopened `pending` and `cellared` rows are owned; verdict rows may also include bottles drunk at restaurants that were never cellared:

- `pending`: owned, awaiting opening-year review.
- `cellared`: owned and unopened.
- `love` / `like` / `meh` / `pass`: already opened and evaluated, whether from the cellar or elsewhere.

For tonight's options, include rows whose `opened_on` is null and whose status is `pending` or `cellared`. Exclude opened bottles and explain exclusions briefly when they were otherwise in scope.

Apply the user's category literally:

- Region/appellation beats stylistic analogy. A Napa "Right Bank-inspired" blend is not Right Bank Bordeaux.
- Actual Right Bank Bordeaux must be from Bordeaux, France, and an applicable Right Bank appellation such as Pomerol, Lalande-de-Pomerol, Saint-Émilion or its satellites, Fronsac/Canon-Fronsac, Castillon, Bourg, or Blaye.
- When the user says "from the latest shopping trip," identify rows added by the relevant staging/addition commit using `git log -- cellar.jsonl` and `git show`. Do not infer the trip from row proximity alone.
- Keep duplicate bottles as one option and state quantity only when it affects the recommendation.

If the resulting set is empty, say so plainly. Do not widen the category without the user asking.

### 3. Load taste evidence

Read `preferences.json` and the relevant `verdict` and `impressions` fields in `cellar.jsonl`.

Extract the active taste axes rather than relying on generic wine doctrine. Tie the ranking to named benchmark bottles when evidence exists. Distinguish:

- traits Andrew likes;
- traits he dislikes;
- the structural relationship causing the preference;
- whether decanting materially changed a benchmark.

Do not reduce a nuanced preference to a crude ban such as "avoid tannin," "avoid limestone," or "avoid high alcohol" when the record shows that balance or integration is the real issue.

### 4. Research decision-relevant gaps

Browse for missing or uncertain vintage-specific details. Source order:

1. Producer vintage page or technical sheet.
2. Wine Advocate, Vinous, Decanter, Wine Spectator, Jancis Robinson, James Suckling, or another named professional critic.
3. Reputable specialist merchant reproducing attributed critic material.
4. Cross-vintage producer context, explicitly labeled as such.

Research only what improves tonight's decision:

- exact blend;
- ABV;
- fermentation and élevage;
- vintage-specific character;
- credible drinking window;
- current maturity;
- appropriate decant and serving temperature.

Keep vintage-specific facts separate from house style. When a technical detail remains unavailable, write "unverified"; do not guess.

### 5. Add price context

Prefer the local Total Wine Centennial #2302 index:

```bash
python3 inventory/query_inventory.py --text "<distinctive bottle terms>" --urls --limit 10
```

Query one candidate at a time. Never load the raw inventory JSONL into model context.

Check the index date:

```bash
git log -1 --format=%cs%x09%h%x09%s -- inventory/totalwine-centennial.jsonl
```

Use the matching vintage's shelf price. Introduce the table with:

> Prices are Centennial Total Wine shelf prices from the local index, last recorded <date>; treat them as context rather than receipt-confirmed purchase prices.

If a bottle is absent, browse for a current reputable retail price and label it `~$XX market`. If the user asks what they personally paid, do not substitute a market price.

### 6. Rank for tonight

Rank by:

1. Fit to Andrew's recorded taste structure.
2. Readiness tonight and benefit from decanting.
3. Intrinsic interest as a standalone drink.
4. Opportunity cost of opening a bottle before its plateau.
5. Meal compatibility only to the extent requested.
6. Price as context or value—not as a proxy for quality.

The best absolute wine is not automatically the best bottle tonight. Penalize a promising bottle when credible evidence says to hold it. State the tradeoff.

### 7. Produce the fixed recommendation format

Lead with a direct call:

> Your Highness, **open the <wine>**. <One sentence connecting it to the taste record and tonight's goal.>

Then render this exact seven-column table:

| Tonight rank | Bottle | Price | Verified composition and élevage | Expected character | Readiness | Service |
|---:|---|---:|---|---|---|---|
| **1** | **<Wine vintage>** — <appellation> | **$XX.XX** | <Exact blend, ABV, fermentation and maturation. Name uncertainty.> | <Specific sensory/structural expectation and why it fits or risks Andrew's preferences.> | <Explicit window and plain ready/young/hold verdict.> | **Decant X; serve Y°F.** <Links to producer and strongest critic/window source.> |

Table rules:

- Preserve full prose. Do not collapse the table into terse shopping blurbs.
- Use the precise bottle name, vintage, and appellation.
- Include composition, élevage, character, readiness, and service for every option.
- Put the ranking number in its own column.
- Put price in its own column.
- Explain why each bottle ranks where it does, especially any taste-fit risk.
- Link sources in the `Service` cell to keep the table readable.
- Use bold only for rank, bottle, price, and actionable service.

After the table:

1. Add a separate food-pairing paragraph if a meal was mentioned. State whether the ranking changes when pairing becomes the priority.
2. Add one short exclusion note for in-scope bottles already opened or otherwise unavailable.
3. Do not append a redundant source list.

## Boundaries

- Recommendation mode is read-only. Do not edit `cellar.jsonl`, set `opened_on`, or assign a verdict merely because a bottle was recommended.
- When Andrew confirms which bottle he opened, use the `wine-cellar` drink-and-feedback workflow.
- Do not turn this into a buying recommendation; use `wine-buying` for bottles not yet owned.
