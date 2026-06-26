---
name: wine-cellar
description: Catalogue wines into and manage the shared Wilterson/EffectorGraph wine-cellar database — entry, review of store-staged bottles, and tasting feedback. Data lives as JSONL in a git repo; an HTML view is auto-regenerated on each edit and both files commit-push to GitHub. Use this skill when the user wants to (1) enter/add/log/cellar a specific wine + vintage ("add the 2019 Opus One", "cellar this: ..."); (2) review bottles staged from a store run and set their target open year ("review my pending bottles", "let's finish logging what I bought"); or (3) leave tasting feedback on a bottle they're drinking ("opening the Porter Cave Dwellers tonight", "let me tell you how that Cab was", "update my notes on X as I get through it"). Also triggers when the user names a specific wine + vintage in a collection-management context. Do NOT use for picking wines to buy at a store (that's the wine-buying skill) or general wine questions (pairings, winery history).
---

# Wine Cellar (JSONL + HTML, git-backed)

You manage the shared wine-cellar database across a bottle's life: **enter** a wine, **review** bottles staged from a store run, and capture **tasting feedback** while drinking. The database lives as a JSONL file in a two-user GitHub repo; an HTML view is auto-regenerated on every edit. The companion **wine-buying** skill handles store recommendations and stages purchases as `pending` rows for this skill to review.

Address the user as "Your Highness". Be concise.

Pick the workflow by intent:
- New bottle to log → **[Per-wine entry workflow](#per-wine-workflow)**
- "Review my pending bottles" / finish logging a store run → **[Review staged bottles](#review-staged-bottles)**
- "Opening / drinking X", leaving or updating a verdict → **[Drink + feedback workflow](#drink--feedback-workflow)**

## Files

- **`<repo>/cellar.jsonl`** — source of truth, one wine per line (34 fields)
- **`<repo>/cellar-view.html`** — auto-generated from JSONL, do not edit by hand
- **`<repo>/preferences.json`** — living likes/dislikes/benchmarks; read by wine-buying, grown as verdicts land
- **`<repo>/skill/scripts/schema.py`** — single source of truth for field order + validation (imported by the others)
- **`<repo>/skill/scripts/append_wine.py`** — appends one row (JSON on stdin)
- **`<repo>/skill/scripts/update_wine.py`** — patches one existing row by wine+vintage (review + feedback)
- **`<repo>/skill/scripts/generate_view.py`** — rebuilds cellar-view.html
- **`<repo>/skill/scripts/test_backend.py`** — round-trip tests for append + update
- **`<repo>/.githooks/pre-commit`** — guards against invalid JSONL, bad status, stale view, behind-remote state

Find `<repo>`: `~/.claude/skills/wine-cellar/.local-config.json` → `repo_path`. Set by `sync_skill.sh` at install time.

## The 34 fields (JSONL schema)

Every row is a JSON object with all 34 keys present: 31 **objective** fields (the wine's facts) followed by 3 **subjective** feedback fields (your verdict). Use `null` for unknown values — do not omit keys. Field order in each line is the order below (for readable git diffs). `schema.py` is the authority — the scripts validate against it.

The feedback layer is ported from the green-tea-log model: a categorical `status` (no numeric scores), a prose `verdict`, and an evolving `impressions` log. Append/update fill these — you don't hand-edit JSONL.

| # | Key | Type | Rule |
|---|---|---|---|
| 1 | `wine` | str | Bottle name as printed on the label (e.g. `"Aonair Mountains Proprietary Reserve"`) |
| 2 | `winery` | str | Producer name, canonical short form. See "Canonical names" below. |
| 3 | `vintage` | int | Year of harvest |
| 4 | `grapes` | str | Comma-separated varietals. Include percentages only if verified from the producer. |
| 5 | `subregion` | str/null | Formal sub-AVA / commune / cru only. Blank if the wine has no formal sub-appellation (e.g. cross-mountain Napa blend, generic "Yarra Valley"). |
| 6 | `region` | str/null | Broader region (Napa Valley, Yarra Valley, Bordeaux, Veneto, etc.) |
| 7 | `country` | str | USA, Australia, France, Italy, etc. |
| 8 | `estate` | str/null | `"Yes"` if grapes from producer's own vineyards, `"No"` if sourced. Blank if mixed/uncertain. |
| 9 | `soil` | str/null | Soil description. Prefix with `~` when AVA-inferred rather than producer-exact (see `~` convention). `"Various"` for multi-AVA blends. |
| 10 | `elevation` | str/null | Text (ft USA, m AU/EU). Same `~` convention as `soil`. |
| 11 | `vine_age` | str/null | Only format: `Planted in "YYYY"` (bare if producer-verified, `~`-prefixed if inferred, `Planted in "YYYY" onwards` for ranges). Blank if unverified. |
| 12 | `importer` | str/null | US importer for non-US wines. `"Self"` if the user imported it themselves. Blank for US wines. |
| 13 | `harvest_date` | str/null | When picked. ISO date (`"2022-09-11"`) if known to the day; month (`"October 2023"`) or range (`"Sept 14-Oct 25, 2022"`) otherwise. |
| 14 | `fermentation_vessel` | str/null | `"Stainless steel"`, `"Concrete"`, `"Open-top fermenters"`, `"Oak"`, or combination. Prefix `~` if inferred. |
| 15 | `whole_bunch_pct` | int/null | Percent of fruit fermented whole-cluster. `0` = destemmed. Blank if not explicitly published. |
| 16 | `malolactic` | str/null | `"Complete"` / `"Partial"` / `"Blocked"`. Blank if not stated. Important for Chardonnay especially. |
| 17 | `barrel_time` | str/null | Producer's élevage duration, e.g. `"22 months"`. Blank if not published. |
| 18 | `oak_origin` | str/null | `"French"`, `"American"`, `"Hungarian"`, `"None (unoaked)"`, or combinations (`"French + Hungarian"`). |
| 19 | `new_oak_pct` | int/null | Integer percent new oak. |
| 20 | `abv` | float/null | Decimal (e.g. `14.6`). |
| 21 | `ph` | float/null | Two-decimal final chemistry. |
| 22 | `ta` | float/null | Titratable Acidity in g/L. Pairs with pH. |
| 23 | `residual_sugar` | float/null | g/L. Convert `%` to g/L: `1%` = `10 g/L`. |
| 24 | `cases_produced` | int/null | 750ml-equivalent cases. |
| 25 | `release_date` | str/null | ISO date or month/year. |
| 26 | `drink_from` | int | Earliest year at plateau. |
| 27 | `cellared_under` | int/null | User's target year to open this bottle. **User supplies this** — do not guess. `null` while a bottle is `pending` (staged at the store, not yet reviewed); filled at review time. |
| 28 | `drink_by` | int | Latest year before decline. |
| 29 | `opened_on` | str/null | ISO date actually opened. Blank while cellared. Cellared Under = *intent*, Opened On = *actual*. |
| 30 | `tasting_notes` | str/null | **STRICT.** Vintage-specific producer/critic notes only. Blank if no vintage-specific note exists. Do NOT generalize from grape/region/adjacent vintage. |
| 31 | `fallback_tasting_notes` | str/null | **LOOSER.** Used only when `tasting_notes` is blank. Cross-vintage, adjacent-vintage, house-style notes — always prefixed with context (`"Cross-vintage:"`, `"2022 vintage:"`, `"House style:"`). |
| 32 | `status` | enum | Lifecycle + verdict in one field: `pending` (staged at store, awaiting review) → `cellared` (reviewed, target year set, not yet drunk) → on drinking, one shared verdict: `love` / `like` / `meh` / `pass`. Default on plain entry: `cellared`. |
| 33 | `verdict` | str/null | The shared, plain-spoken summary judgment (one or two sentences). Rendered italic in the view. Blank until drunk. This is **your** voice, not a critic's — keep `tasting_notes`/`fallback` for sourced notes. |
| 34 | `impressions` | array | Evolving log of how it actually drank: `[{"date": "2026-06-26", "note": "..."}]`. Append-only — first pour, after it opens up, last glass, next-day recork. Empty `[]` until drunk. |

## Per-wine workflow

1. **Parse the request.** Identify wine + vintage. If vintage missing or ambiguous (multiple bottlings, e.g. Napa vs. Sonoma), **ask**. Do not guess.
2. **Research.** Use WebSearch and WebFetch. Source priority: producer tech sheets (gold), Halliday / Wine Spectator / Vinous / Wine Advocate / Decanter / Suckling, CellarTracker consensus, Wine-Searcher, Vivino (last resort).
3. **Separate vintage-specific from cross-vintage.** Note from a different vintage or general description goes in `fallback_tasting_notes`, NOT `tasting_notes`.
4. **Propose a drink window.** Base on vintage quality, house style, oak/structure, critic projections. If a critic/producer gives an explicit window, cite them in the Tasting Notes cell and use their window. If the window is my analysis, don't write anything implying external sourcing.
5. **Report to user** in this format:
   - Small table: Winery · Vintage · Grapes · Subregion / Region / Country · Importer (if any)
   - Vintage-specific tasting note (or "no vintage-specific note found")
   - Proposed Fallback if column 30 blank
   - **Suggested window: YYYY – YYYY** with one-line rationale
   - Sources (markdown links)
6. **Ask for Cellared Under.** Wait for user to supply the target year and confirm or override other fields.
7. **Orchestrate the commit** (see Git Sync Workflow below).
8. **Verify.** Report row count, whether view regenerated, and whether push succeeded.

## Review staged bottles

When the user says "review my pending bottles" / "let's finish logging the store run", they're filling in the **opinion** field the wine-buying skill left blank: `cellared_under` (their target open year). The research is already done — these rows are complete except for that.

1. **Find pending rows.** Read `cellar.jsonl`; list every row with `status: "pending"`. For each, show the small report (winery · vintage · grapes · region · suggested drink window from `drink_from`/`drink_by`).
2. **Ask for `cellared_under`** per bottle (target year to open). One question per bottle, or batch them.
3. **Patch each** via `update_wine.py` — set `cellared_under` and flip `status` to `cellared`:
   ```bash
   python3 skill/scripts/update_wine.py <<'JSON'
   { "match": {"wine": "<exact name>", "vintage": 2021},
     "set": {"cellared_under": 2030, "status": "cellared"} }
   JSON
   ```
4. Regenerate view → commit (`Review: set cellared-under for <wine> <vintage>`) → push. See Git sync workflow.

## Drink + feedback workflow

When the user is opening / drinking a bottle and wants the story plus to leave a verdict. This is the green-tea-log feedback loop — **prose and vibes, no scores.**

1. **Surface the bottle.** Find its row by name (+ vintage if ambiguous). Print the made-how / vendor / window: grapes, region, estate, fermentation, oak, ABV, drink window, and any `tasting_notes`/`fallback_tasting_notes`. This is the "how was it made" the user wants in hand while sipping.
2. **Talk it through.** Capture impressions as they come. The user may give one verdict, or evolve it across the night / next day — **append, don't overwrite.** Each `impressions` entry is `{date, note}`; label the moment in the note ("first pour", "+45 min", "last glass", "recorked, day 2").
3. **Patch via `update_wine.py`:**
   - First sitting: set `opened_on` (ISO date), append the first impression, set a `verdict` and `status` (`love`/`like`/`meh`/`pass`).
     ```bash
     python3 skill/scripts/update_wine.py <<'JSON'
     { "match": {"wine": "<exact name>", "vintage": 2019},
       "set": {"status": "like", "verdict": "<one or two plain-spoken sentences>", "opened_on": "2026-06-26"},
       "append_impression": {"date": "2026-06-26", "note": "First pour: tight, opens after 30 min."} }
     JSON
     ```
   - Coming back mid-bottle / next day: just `append_impression` (and refine `verdict`/`status` if the take changed).
4. **Offer to update `preferences.json`** when a verdict reveals a style-level like/dislike ("savory not jammy", "too oaky") or a new benchmark. Edit it directly (it's a plain JSON object) and stage it with the same commit.
5. Regenerate view → commit (`Feedback: <wine> <vintage> — <status>`) → push.

**Verdict voice:** match the user's green-tea-log register — terse, declarative, a little colloquial ("Punches above its weight", "Fell flat after 20 minutes"). Write the verdict in the user's voice from what they tell you; don't invent sensory detail they didn't give.

## Git sync workflow (the orchestration)

After the user confirms, execute these steps in order via Bash:

```bash
REPO="$(python3 -c "import json,pathlib;print(json.loads(pathlib.Path.home().joinpath('.claude/skills/wine-cellar/.local-config.json').read_text())['repo_path'])")"
cd "$REPO"

# 1. Pull latest (fail loud on non-fast-forward)
git pull --ff-only

# 2. Append the row (JSON on stdin as heredoc — single command, no pipe)
python3 skill/scripts/append_wine.py <<'JSON'
{ ...the JSON payload with all 31 keys... }
JSON

# 3. Regenerate the view
python3 skill/scripts/generate_view.py

# 4. Stage both files
git add cellar.jsonl cellar-view.html

# 5. Commit (pre-commit hook runs)
git commit -m "Add <wine name> <vintage>"

# 6. Push
git push
```

**Commit message conventions:**
- New row: `Add <wine> <vintage>` (e.g. `Add Porter Family Vineyards Barre Azure 2023`)
- Staged purchases (wine-buying): `Stage N bottles from <shop/date>`
- Review (set cellared-under): `Review: set cellared-under for <wine> <vintage>`
- Feedback (drinking): `Feedback: <wine> <vintage> — <status>`
- Other update: `Update <wine>: <reason>` (e.g. `Update Aonair Mountains 2021: add Opened On 2026-10-15`)
- Schema / code: `Schema: <change>` or `Skill: <change>`

For review/feedback, **step 2 of the orchestration uses `update_wine.py`** (patch by wine+vintage) instead of `append_wine.py`. Everything else — pull, regenerate, add, commit, push — is identical.

**On pull failure (non-fast-forward):** report the conflict to the user — do not auto-resolve. Typical cause: husband has pushed commits since the user's last pull. Tell the user to manually sort it out via `git pull --rebase` or ask for guidance.

**On pre-commit hook failure:**
- "Invalid JSON on line N" → cellar.jsonl is corrupt; inspect and fix
- "Stale view" → rerun `python3 skill/scripts/generate_view.py` (you may have forgotten step 3)
- "Behind remote" → rerun from step 1

## Path discovery (inside the scripts)

`append_wine.py` and `generate_view.py` resolve `cellar.jsonl` via:
1. `WINE_CELLAR_PATH` env var (absolute path, override)
2. `~/.claude/skills/wine-cellar/.local-config.json` → `{"repo_path": "..."}` → `repo_path + /cellar.jsonl`
3. Error — instruct user to run `sync_skill.sh`

`.local-config.json` is written by `sync_skill.sh` and is gitignored (per-user).

## The `~` convention — inferred values

Used on `soil`, `elevation`, `vine_age`, and `fermentation_vessel` when the value isn't producer-exact:
- **Bare value** = producer tech sheet / critic review / direct label reading
- **`~` prefix** = AVA-level characterization, adjacent-vintage inference, or recalled fact not re-verified in this session
- **`"Various"`** = structural descriptor for multi-AVA blends; not prefixed
- **Blank** = unknown, not worth guessing

Doesn't apply to numeric types (int/float can't be prefixed) — for those, blank = unknown. Doesn't apply to `tasting_notes` (the strict/fallback split already encodes provenance there).

## Research discipline — don't give up on tech specs too fast

When a producer is small / allocation-only and the specific vintage isn't on a tech sheet, **don't default to `null` immediately**. Instead:
1. Check adjacent vintages — producer tech sheets often use a predictable URL pattern (e.g. `/2023Vintage/2023X.pdf`). Try 2022, 2019, 2020.
2. If adjacent vintages have tech sheets, note the pattern in `fallback_tasting_notes` — e.g. `"2017 tech sheet shows 12 months / 35% new French oak, consistent producer method; 2023 not publicly located"`. Honest and useful.
3. Only `null` tech specs when you've actually looked and the producer doesn't publish them.

Applies most to: `barrel_time`, `new_oak_pct`, `oak_origin`, `cases_produced`, `abv`, `ph`, `ta`, `residual_sugar`, `release_date`.

## Common pitfalls — audited from real errors

1. **Winery shortname drift** — `"Porter"` instead of `"Porter Family Vineyards"`. Match existing rows exactly.
2. **Tasting Notes AND Fallback both populated** — violates strict/fallback split. Fallback is used ONLY when Tasting Notes is blank. Merge context into Tasting Notes with a `"| Producer/house context: ..."` suffix if needed.
3. **Informal-locality Subregion** — `"Main Ridge"` (Mornington), `"Gruyere"` (Yarra Valley) are NOT formal GIs. Keep `subregion` null.
4. **Non-canonical importer** — use `"Self"` not `"Self-imported"`.
5. **Non-standard Vine Age** — `"~25 years"` isn't acceptable. Only `Planted in "YYYY"`. Blank if only average age is known.
6. **Subregion naming variants** — `"Carneros"` vs `"Los Carneros"` for the same AVA. Check existing rows and match.
7. **Soil/elevation divergence across same producer** — if a Porter Coombsville row says `"~Volcanic tuff, clay loam"`, use that exact string for the next Porter Coombsville wine.
8. **Over-narrow elevation bands** — for AVA-inferred (`~`-prefixed) values, match the AVA-level range other rows use, not a guess at a narrower vineyard-specific band.
9. **Forgot to regenerate view** — pre-commit hook will catch it, but it wastes a commit attempt.
10. **Forgot to pull before edit** — causes rejected push. Always start with `git pull --ff-only`.

### Canonical short forms (keep matching)

| Category | Canonical | Do NOT use |
|---|---|---|
| Porter's producer name | `"Porter Family Vineyards"` | `"Porter"` |
| Aonair's producer name | `"Aonair"` | `"Aonair Winery & Caves"`, `"Aonair Wines"` |
| Self-imported wine | `"Self"` | `"Self-imported"`, `"Self (by user)"` |
| No oak at all | `"None (unoaked)"` or `"None"` | `"Neutral"`, `"N/A"`, `""` |

Add entries as they come up. When in doubt, match the most-recent existing row's format.

## Subregion rule for informal localities — keep blank

**Informal localities (Subregion = blank):**
- **Mornington Peninsula, Australia:** Main Ridge, Red Hill, Merricks, Balnarring, Tuerong, Dromana.
- **Yarra Valley, Australia:** Gruyere, Warramate, Coldstream.
- **Russian River Valley, USA:** Middle Reach, Sebastopol Hills (except Green Valley of RRV, which IS an AVA).
- **Cross-mountain Napa blends** labeled just "Napa Valley" on the bottle.

**Formal GIs (Subregion = populated):**
- Napa sub-AVAs: Coombsville, Rutherford, Oakville, Atlas Peak, Howell Mountain, Mt. Veeder, Spring Mountain, Diamond Mountain, Stags Leap District, Yountville, Calistoga, St. Helena, Wild Horse Valley, Los Carneros (cross-county), Oak Knoll, Chiles Valley.
- Sonoma AVAs: Russian River Valley, Alexander Valley, Dry Creek Valley, Sonoma Valley, Los Carneros, Sonoma Coast, Fort Ross-Seaview, Bennett Valley, Green Valley of RRV.
- Sierra Foothills: El Dorado, Amador County, Shenandoah Valley, Fiddletown, Fair Play.
- Italy (DOCG/DOC): Gambellara, Barolo, Barbaresco, Chianti Classico, etc.

When in doubt: check if the AVA/GI is registered with the relevant authority (TTB for USA, EU GI database for Europe, Wine Australia for AU). If not, it's informal → blank.

## Vine Age — strict format

Only these formats are acceptable:
- `Planted in "YYYY"` (verified, producer-stated)
- `~Planted in "YYYY"` (inferred from adjacent source — not live-verified)
- `Planted in "YYYY" onwards` (estate planted over decades, earliest verified year)
- `Planted in "YYYY-YYYY"` (verified range)

**Do NOT use:**
- `"~25 years (producer, average)"` — average age isn't a planting year
- `"Old vines"` — vague, not portable
- `"Mature vines"` — same problem

If only an average or vague descriptor is available, **leave blank** and note the detail in `fallback_tasting_notes`.

## Tone and style

- Address the user as "Your Highness"
- Be concise; skip preamble
- Quote tasting notes verbatim with proper attribution (`Producer: "..."`, `Halliday (98 pts): "..."`, etc.)
- Treat `null` as honest; don't pad blanks with "TBD" or placeholder text
- When uncertainty exists, name it once (via the `~` convention or a Fallback note) and move on

## Bash style (honor user's global CLAUDE.md)

- No piped (`|`) or chained (`&&`, `;`) bash commands in tool calls — one command per Bash invocation
- Heredocs are one command: `python3 append_wine.py <<'JSON' ... JSON` is fine
- Prefer Grep / Glob / Read over grep / find / cat

## Reference workflow

User says: "Aonair Mountains Reserve 2021"

1. Research: Aonair Winery, 2021 vintage, Bordeaux blend from Atlas Peak / Howell / Mt. Veeder / Diamond / Spring Mountain sources
2. Report: blend, cross-mountain sourcing → Subregion blank, Region Napa Valley, Country USA, Estate No, no vintage-specific critic note for 2021, propose 2028–2043 window
3. User: "Cellared Under 2031"
4. Orchestrate: pull → append_wine.py with JSON payload → generate_view.py → git add → commit "Add Aonair Mountains Proprietary Reserve 2021" → push
5. Verify: 54 rows now, HTML regenerated, push succeeded
