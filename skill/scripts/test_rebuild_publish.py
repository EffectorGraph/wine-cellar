"""Integration tests for rebuild_publish.py using only temporary local Git repos."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("rebuild_publish.py")
BRANCH = "codex/phone-cellar"


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class RebuildPublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="wine-cellar-rebuild-test-")
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        self.work = self.root / "work"
        self.bin = self.root / "bin"
        self.real_git = shutil.which("git")
        if not self.real_git:
            self.fail("git is required for rebuild_publish integration tests")
        subprocess.run([self.real_git, "init", "--bare", str(self.remote)], check=True, capture_output=True, text=True)
        self._make_fixture_repo()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_fixture_repo(self) -> None:
        subprocess.run([self.real_git, "init", str(self.seed)], check=True, capture_output=True, text=True)
        git("config", "user.name", "Fixture User", cwd=self.seed)
        git("config", "user.email", "fixture@example.invalid", cwd=self.seed)
        (self.seed / "skill/scripts").mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.seed / "skill/scripts/rebuild_publish.py")
        (self.seed / "cellar.jsonl").write_text('{"wine":"seed-row"}\n', encoding="utf-8")
        (self.seed / "cellar-view.html").write_text("seed view\n", encoding="utf-8")
        (self.seed / "index.html").write_text("seed index\n", encoding="utf-8")
        (self.seed / "skill/scripts/validate_cellar.py").write_text(
            "import os, sys\nsys.exit(int(os.environ.get('VALIDATOR_EXIT', '0')))\n", encoding="utf-8"
        )
        (self.seed / "skill/scripts/test_backend.py").write_text("pass\n", encoding="utf-8")
        (self.seed / "skill/scripts/generate_view.py").write_text(
            "from pathlib import Path\n"
            "source = Path('cellar.jsonl').read_text()\n"
            "Path('cellar-view.html').write_text('view from: ' + source)\n"
            "Path('index.html').write_text('index from: ' + source)\n",
            encoding="utf-8",
        )
        git("add", ".", cwd=self.seed)
        git("commit", "-m", "Seed fixture", cwd=self.seed)
        git("branch", "-M", BRANCH, cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "-u", "origin", BRANCH, cwd=self.seed)
        git("--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/" + BRANCH, cwd=self.root)
        git("clone", str(self.remote), str(self.work), cwd=self.root)
        git("config", "user.name", "Fixture User", cwd=self.work)
        git("config", "user.email", "fixture@example.invalid", cwd=self.work)
        git("config", "core.hooksPath", "/dev/null", cwd=self.work)

    def _git_wrapper(self, race: bool) -> Path:
        write_executable(
            self.bin / "git",
            "#!/usr/bin/env python3\n"
            "import os, pathlib, subprocess, sys\n"
            "real = os.environ['REAL_GIT']\n"
            "args = sys.argv[1:]\n"
            "if args[:1] == ['push']:\n"
            "    log = pathlib.Path(os.environ['PUSH_LOG'])\n"
            "    with log.open('a') as f: f.write('push\\n')\n"
            "    marker = pathlib.Path(os.environ['RACE_MARKER'])\n"
            "    if os.environ.get('RACE_PUSH') == '1' and not marker.exists():\n"
            "        marker.touch()\n"
            "        remote = os.environ['RACE_REMOTE']\n"
            "        clone = pathlib.Path(os.environ['RACE_CLONE'])\n"
            "        subprocess.run([real, 'clone', remote, str(clone)], check=True, stdout=subprocess.DEVNULL)\n"
            "        subprocess.run([real, 'config', 'user.name', 'Concurrent Writer'], cwd=clone, check=True)\n"
            "        subprocess.run([real, 'config', 'user.email', 'writer@example.invalid'], cwd=clone, check=True)\n"
            "        cellar = clone / 'cellar.jsonl'\n"
            "        cellar.write_text(cellar.read_text() + '{\\\"wine\\\":\\\"remote-row\\\"}\\n')\n"
            "        subprocess.run([real, 'add', 'cellar.jsonl'], cwd=clone, check=True)\n"
            "        subprocess.run([real, 'commit', '-m', 'Concurrent source update'], cwd=clone, check=True, stdout=subprocess.DEVNULL)\n"
            "        subprocess.run([real, 'push', 'origin', 'HEAD:refs/heads/' + os.environ['GITHUB_REF_NAME']], cwd=clone, check=True, stdout=subprocess.DEVNULL)\n"
            "result = subprocess.run([real, *args])\n"
            "sys.exit(result.returncode)\n",
        )
        return self.bin

    def _run_rebuild(self, *, race: bool = False, validator_exit: int = 0) -> tuple[subprocess.CompletedProcess[str], Path]:
        wrapper_dir = self._git_wrapper(race)
        push_log = self.root / "pushes.log"
        env = dict(os.environ)
        env.update({
            "PATH": str(wrapper_dir) + os.pathsep + env.get("PATH", ""),
            "REAL_GIT": str(self.real_git),
            "GITHUB_ACTIONS": "true",
            "GITHUB_REF_NAME": BRANCH,
            "WINE_CELLAR_PATH": str(self.work / "cellar.jsonl"),
            "VALIDATOR_EXIT": str(validator_exit),
            "PUSH_LOG": str(push_log),
            "RACE_MARKER": str(self.root / "race.done"),
            "RACE_REMOTE": str(self.remote),
            "RACE_CLONE": str(self.root / "racer"),
            "RACE_PUSH": "1" if race else "0",
        })
        result = subprocess.run(
            [sys.executable, "skill/scripts/rebuild_publish.py"],
            cwd=self.work, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return result, push_log

    def test_concurrent_source_push_rebuilds_latest_and_commits_only_generated_files(self) -> None:
        result, _ = self._run_rebuild(race=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("rereading remote data", result.stdout)

        remote_clone = self.root / "verify"
        subprocess.run([self.real_git, "clone", str(self.remote), str(remote_clone)], check=True, capture_output=True, text=True)
        source = (remote_clone / "cellar.jsonl").read_text(encoding="utf-8")
        self.assertIn("seed-row", source)
        self.assertIn("remote-row", source)
        generated = (remote_clone / "cellar-view.html").read_text(encoding="utf-8")
        self.assertIn("remote-row", generated)
        self.assertIn("remote-row", (remote_clone / "index.html").read_text(encoding="utf-8"))

        latest = git("rev-parse", "HEAD", cwd=remote_clone)
        paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", latest, cwd=remote_clone).splitlines()
        self.assertEqual(set(paths), {"cellar-view.html", "index.html"})
        parent = git("rev-parse", latest + "^", cwd=remote_clone)
        self.assertEqual(parent, git("rev-parse", "HEAD", cwd=self.root / "racer"))

    def test_validation_failure_stops_without_pushing(self) -> None:
        before = git("rev-parse", "refs/heads/" + BRANCH, cwd=self.remote)
        result, push_log = self._run_rebuild(validator_exit=7)
        after = git("rev-parse", "refs/heads/" + BRANCH, cwd=self.remote)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, after)
        self.assertFalse(push_log.exists() and push_log.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
