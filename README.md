# Wine Cellar

A shared wine-cellar database for the Wilterson household. Data lives as JSONL, with an auto-generated HTML view for browsing. Editing happens primarily via Claude Code using two bundled skills.

## The bottle lifecycle

The repo tracks a bottle from shelf to last glass, as a loop:

1. **Buy** — at the store, the **`wine-buying`** skill reads shelf photos, recommends what to grab based on what you've loved/passed (`cellar.jsonl` verdicts + `preferences.json`), and stages each purchase as a `pending` row.
2. **Review** — the **`wine-cellar`** skill surfaces `pending` bottles so you set a target opening year; they flip to `cellared`.
3. **Drink** — when you open one, `wine-cellar` shows how it was made and captures your **verdict** + an evolving **impressions** log (`love`/`like`/`meh`/`pass`).

Each verdict feeds the next shopping trip. Every row carries 34 fields: 31 objective facts + 3 subjective feedback fields (`status`, `verdict`, `impressions`).

## Store inventory (Total Wine Centennial #2302)

So shopping isn't slow guesswork, the repo keeps a **live local index of every in-stock wine over $20** at Total Wine #2302 — price, stock count, and shelf aisle per wine — in `inventory/totalwine-centennial.jsonl`. At the store, `inventory/query_inventory.py` filters it and prints only the matches (token-tight, no live scraping).

- **Refresh at home** (never at the store): the **`wine-inventory-refresh`** skill, or `bash inventory/refresh_inventory.sh`. It drives a local browser past Total Wine's bot-wall, reads the store's listing data, reconciles against the existing index (only real changes are written), and commits the diff.
- **Automate it:** `bash inventory/install_schedule.sh` once installs a **biweekly launchd job** that refreshes unattended in your login session.
- How it works + troubleshooting: see `wine-inventory-refresh/SKILL.md` and the repo `CLAUDE.md`.

## What's in the repo

| File | Role |
|---|---|
| `cellar.jsonl` | **Source of truth.** One JSON object per wine, 34 fields. Edit via the skills, not by hand (but manual edits ARE allowed — see below). |
| `cellar-view.html` | **Auto-generated** sortable/filterable table — status badges, pending-review surfacing, verdicts, impressions. Regenerated on every edit. Don't edit by hand. |
| `preferences.json` | Living likes / dislikes / benchmarks taste profile. Read by `wine-buying` to drive recommendations; grows as verdicts land. |
| `skill/SKILL.md` | The `wine-cellar` skill: entry, review of pending bottles, drink feedback. |
| `wine-buying/SKILL.md` | The `wine-buying` skill: shelf photos → recommend → stage purchases. Shares this repo's backend. |
| `skill/scripts/schema.py` | Single source of truth for field order + validation. Imported by the other scripts and the pre-commit hook. |
| `skill/scripts/append_wine.py` | Appends one row of JSONL. |
| `skill/scripts/update_wine.py` | Patches one existing row by wine+vintage (review + feedback). |
| `skill/scripts/generate_view.py` | Rebuilds `cellar-view.html` from `cellar.jsonl`. |
| `skill/scripts/test_backend.py` | Round-trip tests for append + update. |
| `skill/scripts/sync_skill.sh` | Installs the three skills (`wine-cellar`, `wine-buying`, `wine-inventory-refresh`) into `~/.claude/skills/` and writes the per-user path config. |
| `inventory/totalwine-centennial.jsonl` | Live in-stock >$20 store index for #2302 (price, stock, aisle). Built by `scan_store.py`. |
| `inventory/scan_store.py` | Walks Total Wine's listing JSON via a local browser → reconciles the store index. |
| `inventory/SCHEMA.md` | **Reference**: row schema + scraping internals (data path, endpoint, in-stock/price logic, gotchas). Read before editing the scanner. |
| `inventory/query_inventory.py` | Store-time filter over the index — prints only matches (token-tight). |
| `inventory/refresh_inventory.sh` + `install_schedule.sh` | Refresh wrapper (pull→scan→commit/push) + biweekly launchd installer. |
| `wine-inventory-refresh/SKILL.md` | The refresh skill: run the scan at home + troubleshooting. |
| `.githooks/pre-commit` | Guards against invalid JSONL, bad `status`, stale view, behind-remote commits. |
| `config.example.json` | Placeholder. The real per-user `.local-config.json` is written by `sync_skill.sh` and gitignored. |

## Sarah's setup — already done

Claude set up the local environment:
- Repo cloned to `~/repos/databases/wine-cellar/`
- Skill installed into `~/.claude/skills/wine-cellar/` via `sync_skill.sh`
- `.local-config.json` written with the local repo path
- Git hooks enabled (`git config core.hooksPath .githooks`)

## Husband's onboarding

### 1. Prereqs

- `git` (comes with macOS, or `brew install git`)
- `gh` (GitHub CLI: `brew install gh`)
- `python3` (comes with macOS 12+)
- No pip packages needed — everything is stdlib-only

### 2. Authenticate GitHub

```bash
gh auth login
```

Pick: `GitHub.com` → `HTTPS` → `Yes (authenticate git)` → `Login with a web browser`. Complete in browser.

### 3. Clone the repo

```bash
mkdir -p ~/repos/databases
cd ~/repos/databases
git clone https://github.com/EffectorGraph/wine-cellar.git
cd wine-cellar
```

### 4. Install the skill

```bash
bash skill/scripts/sync_skill.sh
```

This copies the skill files into `~/.claude/skills/wine-cellar/` and writes a `.local-config.json` telling the scripts where your clone lives.

### 5. Enable the safety hooks

```bash
git config core.hooksPath .githooks
```

This enables the pre-commit hook that catches invalid JSONL, stale HTML view, and behind-remote commits.

### 6. Restart Claude Code

Close and reopen your Claude session. The skill will pick up the new config on restart.

### 7. Try it

Say "add a wine to the cellar" followed by any wine name and vintage. The skill should:
- Pull latest from GitHub
- Look up the wine and propose details
- Ask for your target opening year
- Append to `cellar.jsonl`, regenerate `cellar-view.html`, commit, and push

## Daily workflow

### Via Claude (primary)

Just say "add <wine name> <vintage>" or "cellar this: <...>". The skill handles research, writing, and git sync. Say "no preference for cellared year, pick one inside the window" if you don't care about the opening-year target.

### Manual edit (backup)

You can edit `cellar.jsonl` directly if the skill isn't available:

1. `git pull --ff-only`
2. Edit a line in `cellar.jsonl` (or append a new one)
3. `python3 skill/scripts/generate_view.py` to regenerate the HTML view
4. `git add cellar.jsonl cellar-view.html`
5. `git commit -m "Update <wine>: <reason>"` (the hook will reject if JSONL is broken or view is stale)
6. `git push`

## Conventions

### Commit messages

- New row: `Add <wine name> <vintage>`
- Staged purchases (wine-buying): `Stage N bottles from <shop/date>`
- Review (set target year): `Review: set cellared-under for <wine> <vintage>`
- Feedback (drinking): `Feedback: <wine> <vintage> — <status>`
- Other update: `Update <wine>: <reason>` (e.g. "Update Aonair 2021: set Opened On 2026-12-24")
- Schema or skill changes: `Schema: <change>` or `Skill: <change>`

### Pull-before-edit

Always `git pull --ff-only` before making any edit. The pre-commit hook will reject a commit if you're behind remote, so if you skip this step you'll find out before push — but you'll still have to re-do the edit on top of latest. Saves hassle to pull first.

### Conflicts

If `git pull` reports a non-fast-forward conflict, it usually means the other user pushed a change since your last pull. Options:
- `git pull --rebase` then resolve any manual conflicts in `cellar.jsonl` (plain text — diff-friendly)
- Or throw away your local work with `git reset --hard origin/main` if you haven't committed yet

The JSONL format was chosen partly to make merges sane: edits to different wines on different lines merge cleanly.

## Optional: GitHub Pages (browse the view online)

The `cellar-view.html` page is self-contained — no external deps — so it can be served via GitHub Pages:

1. In repo Settings → Pages
2. Source: `Deploy from a branch` → `main` / `/ (root)`
3. Save
4. After a minute or two, browse at `https://effectorgraph.github.io/wine-cellar/cellar-view.html`

Nice for sharing with friends/family who don't have GitHub access. Totally optional.

## File roles summary

- **Source of truth: `cellar.jsonl`**. Everything downstream derives from it.
- **Derived: `cellar-view.html`**. Never edit by hand — the pre-commit hook will probably reject it anyway.
- **Per-user: `.local-config.json`**. Written by `sync_skill.sh`, not committed.
- **Committed: everything else.**
