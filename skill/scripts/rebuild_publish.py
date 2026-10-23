#!/usr/bin/env python3
"""CI-only rebuild; bounded non-force retries against current source data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("CI only; use generate_view.py locally.")
    branch = os.environ["GITHUB_REF_NAME"]
    if branch not in {"main", "codex/phone-cellar"}:
        raise SystemExit("Unsupported publication branch")
    root = Path.cwd()
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(3):
        run("git", "fetch", "origin", branch)
        run("git", "checkout", "--detach", "FETCH_HEAD")
        source = run("git", "rev-parse", "HEAD", capture_output=True).stdout.strip()
        run(sys.executable, "skill/scripts/validate_cellar.py")
        run(sys.executable, "skill/scripts/test_backend.py")
        env = dict(os.environ, WINE_CELLAR_PATH=str(root / "cellar.jsonl"), SOURCE_COMMIT=source)
        run(sys.executable, "skill/scripts/generate_view.py", env=env)
        run("git", "add", "--", "cellar-view.html", "index.html")
        changed = subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode
        if changed not in (0, 1):
            raise SystemExit("Cannot inspect generated changes")
        if changed:
            run("git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "Rebuild cellar view")
        pushed = subprocess.run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"])
        if pushed.returncode == 0:
            site = root / "_site"
            site.mkdir(exist_ok=True)
            for name in ("cellar-view.html", "index.html"):
                shutil.copyfile(root / name, site / name)
            (site / ".nojekyll").touch()
            print(f"Rebuilt source {source}. Generated files saved; publication is a separate step.")
            return
        print(f"Push failed ({attempt + 1}/3); rereading remote data before rebuilding.")
    raise SystemExit("Data may be saved, but rebuild push failed after three attempts.")

if __name__ == "__main__":
    main()
