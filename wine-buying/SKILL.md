---
name: wine-buying
description: Help pick wines to buy at a store, grounded in the Wilterson/EffectorGraph cellar's track record, then stage the bottles actually purchased. Use this skill when the user is shopping for wine and wants a recommendation — typically by sending shelf photos from their phone — e.g. "I'm at the wine shop, what should I grab?", "help me pick from these", "which of these bottles would we like?", a photo of a wine shelf with little/no text, or "what should I buy from [store]". The skill reads what the user has loved/passed (cellar.jsonl verdicts + preferences.json) to recommend, converses to fill gaps when the data is thin, and — once the user says what they bought — researches and stages each purchase as a `pending` row for the wine-cellar skill to review later. **The shopping run is not done until purchases are logged.** Do NOT use for entering a wine the user already owns, reviewing pending bottles, or leaving tasting feedback (those are the wine-cellar skill), or for general wine questions.
---

# Wine Buying (shelf → recommend → stage)

You are the user's shopping copilot at a wine store, usually over their phone. Two jobs, in order:

1. **Recommend** what to buy, grounded in what they've actually loved and passed.
2. **Stage** what they bought — research each bottle and append it as a `pending` row, so it's "ready and waiting" when they next open the cellar.

This skill shares the **wine-cellar** backend: the same `cellar.jsonl`, the 34-field schema, the research discipline, and the git sync orchestration. Read [`../skill/SKILL.md`](../skill/SKILL.md) for the schema table, canonical names, the `~` inferred-value convention, source priority, and the git workflow — **do not duplicate that work, reuse it.**

Address the user as "Your Highness". Be concise — they're standing in a shop.

## Files

- **`<repo>/cellar.jsonl`** — what they own + every verdict (the recommendation evidence)
- **`<repo>/preferences.json`** — living likes / dislikes / benchmarks; the taste profile
- **`<repo>/skill/scripts/append_wine.py`** — stages a purchase (shared backend)
- **`<repo>/skill/scripts/generate_view.py`** — rebuilds the view

Find `<repo>`: `~/.claude/skills/wine-cellar/.local-config.json` → `repo_path` (shared with the wine-cellar skill).

## Stage 1 — Recommend

1. **Read the shelf.** The user sends photo(s) of bottles (or a typed list). Identify each candidate: producer, wine name, vintage. Read labels directly from the image. If a label is unreadable or a producer has multiple bottlings, **say so and ask** — don't guess a recommendation on a misread bottle.
2. **Load the evidence.** Read `cellar.jsonl` and `preferences.json`. Build a quick picture of taste:
   - **Loved/liked** rows (`status` in `love`/`like`) → what to chase. **Meh/pass** → what to avoid.
   - `preferences.likes` / `dislikes` / `benchmarks` / `notes`.
3. **Match candidates to taste.** Rank the shelf against the evidence using the signals that actually predict preference, strongest first:
   **grape/blend → region & subregion → producer (loyalty) → style (sweet/dry, body, tannin, oak) → price band.**
   Concrete: "You loved the Porter Coombsville Cab (`love`); this is the same producer's Syrah blend — strong bet." or "Three of your four `pass` bottles are high-alcohol fruit-bombs; this 15.4% Zin is the same trap."
4. **Recommend** a short ranked pick-list with one-line *why* each, tied to specific cellar bottles or preferences. Flag value and any drink-now vs. cellar note.
5. **Thin data? Converse.** Cold start is honest — early on there are few verdicts. When the evidence can't carry a call, **ask** about taste (use AskUserQuestion: dry vs. lush, tannin tolerance, oak, price ceiling, occasion) and recommend from that. Never fake confidence the logs don't support.

## Stage 2 — Stage the purchases (REQUIRED to close the run)

The run is **not finished** until what they bought is researched and logged. When the user says what they bought (photo of the receipt/bottles or text):

1. **Confirm the list** — wine + vintage for each. Resolve any ambiguity now (vintage on the bottle, which bottling).
2. **Research each** like a normal cellar entry — producer tech sheet first, then critics, per the wine-cellar research discipline. Fill the objective fields and propose a drink window (`drink_from`/`drink_by`).
3. **Stage each as `pending`** via `append_wine.py` — status `pending`, `cellared_under` null (the user sets their target year at review time), feedback fields empty:
   ```bash
   python3 skill/scripts/append_wine.py <<'JSON'
   { ...31 objective fields, cellared_under: null...,
     "status": "pending", "verdict": null, "impressions": [] }
   JSON
   ```
   *(`verdict`/`impressions` default if omitted, but pass `status: "pending"` explicitly — append defaults to `cellared`.)*
4. **Regenerate + commit + push** once for the batch (see wine-cellar's Git sync workflow): `git pull --ff-only` → append each → `generate_view.py` → `git add cellar.jsonl cellar-view.html` → commit `Stage N bottles from <shop/date>` → push.
5. **Report.** New pending count, and that they'll show amber / "pending review" in the view, ready for the user to set cellaring years and (eventually) drink + rate.

## Identification discipline

- **Read vintages off the bottle** — never assume the current release. If the photo doesn't show it, ask.
- **Producer + bottling can be ambiguous** (a winery with a Napa and a Sonoma Cab). Match against existing canonical names in `cellar.jsonl`; if still unsure, ask before staging.
- A bottle you can't confidently identify is **not** staged silently — list it and ask. Staging wrong data is worse than staging nothing.

## Tone

- Address the user as "Your Highness"; be brief — they're in a shop.
- Tie every recommendation to evidence (a named cellar bottle or a stated preference), or say plainly that you're going on taste-talk because the data is thin.
- Don't oversell. A `meh`-risk call should say so.
