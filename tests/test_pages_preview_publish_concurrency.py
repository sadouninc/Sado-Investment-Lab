"""#986: lossless, bounded-retry publish to the shared `pages-previews` branch.

Executes the real `Publish preview namespace` bash from publish-site.yml
against synthetic bare git repositories (no network, no GitHub).

担当: ♦️ソラ
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-site.yml"
HEAD = "a" * 40
OTHER = "b" * 40


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _preview_steps() -> list[dict]:
    return _workflow()["jobs"]["preview"]["steps"]


def _step(name: str) -> dict:
    return next(step for step in _preview_steps() if step.get("name") == name)


PUBLISH_SCRIPT = _step("Publish preview namespace")["run"]


def git(*args: str, cwd: Path, check: bool = True) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    result = subprocess.run(["git", *args], cwd=cwd, env=env, text=True,
                            capture_output=True, check=check)
    return result.stdout.strip()


class Sandbox:
    """A bare 'origin', a workspace clone (like actions/checkout) and a fake gh."""

    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        git("init", "--quiet", "--bare", str(self.origin), cwd=root)
        git("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.origin)
        seed = root / "seed"
        git("init", "--quiet", "-b", "main", str(seed), cwd=root)
        (seed / "README.md").write_text("repo\n")
        git("add", ".", cwd=seed)
        git("commit", "--quiet", "-m", "init", cwd=seed)
        git("push", "--quiet", str(self.origin), "main", cwd=seed)
        self.bin = root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        # Fake `gh api .../pulls/N --jq .head.sha`: either a fixed head, or one
        # head per call from a sequence file (last line repeats).
        gh.write_text(textwrap.dedent("""\
            #!/bin/sh
            if [ -n "${FAKE_PR_HEAD_SEQ:-}" ]; then
              n=$(cat "${FAKE_PR_HEAD_SEQ}.count" 2>/dev/null || echo 0); n=$((n+1))
              echo "$n" > "${FAKE_PR_HEAD_SEQ}.count"
              line=$(sed -n "${n}p" "${FAKE_PR_HEAD_SEQ}")
              [ -n "$line" ] || line=$(tail -n 1 "${FAKE_PR_HEAD_SEQ}")
              echo "$line"
            else
              echo "${FAKE_PR_HEAD}"
            fi
            """))
        gh.chmod(0o755)

    def workspace(self, name: str) -> Path:
        path = self.root / name
        git("clone", "--quiet", str(self.origin), str(path), cwd=self.root)
        return path

    def site(self, name: str, files: dict[str, str]) -> Path:
        path = self.root / name
        for rel, content in files.items():
            target = path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return path

    def seed_namespace(self, namespace: str, files: dict[str, str]) -> str:
        """Put content on pages-previews as another writer would."""
        other = self.root / f"other-{namespace}-{len(list(self.root.iterdir()))}"
        git("clone", "--quiet", str(self.origin), str(other), cwd=self.root)
        exists = git("ls-remote", str(self.origin), "refs/heads/pages-previews", cwd=other)
        if exists:
            git("checkout", "--quiet", "-B", "pages-previews", "origin/pages-previews", cwd=other)
        else:
            git("checkout", "--quiet", "--orphan", "pages-previews", cwd=other)
            git("rm", "-rf", "--quiet", ".", cwd=other)
        for rel, content in files.items():
            target = other / namespace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        git("add", "-A", cwd=other)
        git("commit", "--quiet", "-m", f"seed {namespace}", cwd=other)
        git("push", "--quiet", "origin", "HEAD:refs/heads/pages-previews", cwd=other)
        return git("rev-parse", "HEAD", cwd=other)

    def run_publish(self, workspace: Path, site: Path, *, pr: int, head: str = HEAD,
                    pr_head: str = HEAD, attempts: int = 5, backoff: int = 0,
                    head_sequence: list[str] | None = None) -> tuple[int, dict, str]:
        output = self.root / f"out-{workspace.name}-{pr}.txt"
        output.write_text("")
        script = self.root / "publish.sh"
        script.write_text(PUBLISH_SCRIPT)
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_PR_HEAD": pr_head,
            "FAKE_PR_HEAD_SEQ": "",
            "GITHUB_OUTPUT": str(output),
            "GITHUB_REPOSITORY": "sadouninc/Sado-Investment-Lab",
            "GITHUB_RUN_ID": "1",
            "GH_TOKEN": "x",
            "PR_NUMBER": str(pr),
            "HEAD_SHA": head,
            "PREVIEW_BRANCH": "pages-previews",
            "PREVIEW_SITE": str(site),
            "PREVIEW_MAX_ATTEMPTS": str(attempts),
            "PREVIEW_BACKOFF_SECONDS": str(backoff),
        }
        if head_sequence:
            seq = self.root / f"seq-{workspace.name}-{pr}.txt"
            seq.write_text("\n".join(head_sequence) + "\n")
            env["FAKE_PR_HEAD_SEQ"] = str(seq)
        proc = subprocess.run(["bash", str(script)], cwd=workspace, env=env, text=True,
                              capture_output=True, timeout=120)
        outputs = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
        return proc.returncode, outputs, proc.stdout + proc.stderr

    def remote_tip(self) -> str:
        return git("rev-parse", "refs/heads/pages-previews", cwd=self.origin, check=False)

    def remote_file(self, path: str, ref: str = "refs/heads/pages-previews") -> str | None:
        result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=self.origin,
                                text=True, capture_output=True)
        return result.stdout if result.returncode == 0 else None

    def install_competitor_hook(self, workspace: Path, *, always: bool) -> None:
        """pre-push hook: another writer lands a commit just before our push."""
        competitor = self.root / "competitor"
        if not competitor.exists():
            git("clone", "--quiet", str(self.origin), str(competitor), cwd=self.root)
        marker = self.root / "competitor.marker"
        hook = workspace / ".git" / "hooks" / "pre-push"
        hook.write_text(textwrap.dedent(f"""\
            #!/bin/sh
            if [ "{'always' if always else 'once'}" = once ] && [ -e "{marker}" ]; then exit 0; fi
            touch "{marker}"
            echo x >> "{marker}.count"
            n=$(wc -l < "{marker}.count" | tr -d ' ')
            cd "{competitor}" || exit 1
            export GIT_AUTHOR_NAME=c GIT_AUTHOR_EMAIL=c@example.com GIT_COMMITTER_NAME=c GIT_COMMITTER_EMAIL=c@example.com
            unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
            git fetch --quiet origin
            if git rev-parse --verify --quiet origin/pages-previews >/dev/null; then
              git checkout --quiet -B pages-previews origin/pages-previews
            else
              git checkout --quiet --orphan pages-previews && git rm -rf --quiet . >/dev/null 2>&1
            fi
            mkdir -p pr-99 && date +%s%N > "pr-99/stamp-$n"
            git add -A && git commit --quiet -m "competitor $n" && git push --quiet origin HEAD:refs/heads/pages-previews
            exit 0
            """))
        hook.chmod(0o755)


class PreviewPublishConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sb = Sandbox(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_publish_creates_branch_and_returns_exact_pushed_ref(self):
        ws = self.sb.workspace("ws")
        site = self.sb.site("site", {"index.html": "PR PREVIEW 8", "preview-metadata.json": HEAD})
        rc, out, log = self.sb.run_publish(ws, site, pr=8)
        self.assertEqual(rc, 0, log)
        self.assertEqual(out["state"], "published")
        self.assertEqual(out["preview_ref"], self.sb.remote_tip())
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "PR PREVIEW 8")
        self.assertIsNone(self.sb.remote_file("README.md"))  # orphan branch, no repo tree

    def test_unrelated_namespace_is_preserved(self):
        self.sb.seed_namespace("pr-7", {"index.html": "PR 7"})
        ws = self.sb.workspace("ws")
        site = self.sb.site("site", {"index.html": "PR 8"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8)
        self.assertEqual(rc, 0, log)
        self.assertEqual(self.sb.remote_file("pr-7/index.html"), "PR 7")
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "PR 8")

    def test_non_fast_forward_race_is_retried_on_fresh_tip_without_force(self):
        self.sb.seed_namespace("pr-7", {"index.html": "PR 7"})
        ws = self.sb.workspace("ws")
        self.sb.install_competitor_hook(ws, always=False)
        site = self.sb.site("site", {"index.html": "PR 8"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8)
        self.assertEqual(rc, 0, log)
        self.assertEqual(out["attempts"], "2")
        self.assertIn("preview push rejected (attempt 1/5)", log)
        tip = self.sb.remote_tip()
        self.assertEqual(out["preview_ref"], tip)
        # Both writers' work survives: the competitor's commit is an ancestor.
        competitor_commit = git("log", "--format=%H", "--grep=competitor", "-1", "refs/heads/pages-previews",
                                cwd=self.sb.origin)
        self.assertTrue(competitor_commit)
        subprocess.run(["git", "merge-base", "--is-ancestor", competitor_commit, tip],
                       cwd=self.sb.origin, check=True)
        self.assertEqual(self.sb.remote_file("pr-7/index.html"), "PR 7")
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "PR 8")
        self.assertTrue(git("ls-tree", "--name-only", "refs/heads/pages-previews", "pr-99/", cwd=self.sb.origin))

    def test_retry_exhaustion_fails_closed_and_never_overwrites_others(self):
        ws = self.sb.workspace("ws")
        self.sb.install_competitor_hook(ws, always=True)
        site = self.sb.site("site", {"index.html": "PR 8"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8, attempts=3)
        self.assertNotEqual(rc, 0)
        self.assertEqual(out.get("state"), "failed")
        self.assertNotIn("preview_ref", out)
        self.assertIn("failed after 3 attempts (no force push)", log)
        self.assertIsNone(self.sb.remote_file("pr-8/index.html"))
        stamps = git("ls-tree", "--name-only", "refs/heads/pages-previews", "pr-99/", cwd=self.sb.origin).split()
        self.assertEqual(len(stamps), 3)  # every competitor commit kept (no force)

    def test_newer_same_pr_head_means_nothing_is_published(self):
        self.sb.seed_namespace("pr-8", {"index.html": "newer head content"})
        before = self.sb.remote_tip()
        ws = self.sb.workspace("ws")
        site = self.sb.site("site", {"index.html": "stale content"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8, head=HEAD, pr_head=OTHER)
        self.assertEqual(rc, 0, log)
        self.assertEqual(out["state"], "superseded")
        self.assertNotIn("preview_ref", out)
        self.assertEqual(self.sb.remote_tip(), before)
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "newer head content")

    def test_republish_replaces_only_own_namespace_and_old_ref_stays_immutable(self):
        ws = self.sb.workspace("ws")
        first = self.sb.site("site1", {"index.html": "v1", "old.html": "gone later"})
        rc, out1, log = self.sb.run_publish(ws, first, pr=8)
        self.assertEqual(rc, 0, log)
        ws2 = self.sb.workspace("ws2")
        second = self.sb.site("site2", {"index.html": "v2"})
        rc, out2, log = self.sb.run_publish(ws2, second, pr=8)
        self.assertEqual(rc, 0, log)
        self.assertNotEqual(out1["preview_ref"], out2["preview_ref"])
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "v2")
        self.assertIsNone(self.sb.remote_file("pr-8/old.html"))
        # The earlier immutable preview URL still resolves to v1.
        self.assertEqual(self.sb.remote_file("pr-8/index.html", out1["preview_ref"]), "v1")

    def test_stale_same_pr_run_does_not_overwrite_newer_head_published_mid_run(self):
        # ❤️レイ 6098961378: the head is current at the first check, then a newer
        # head publishes this PR's namespace before the old run pushes.
        newer = self.sb.seed_namespace("pr-8", {"index.html": "newer head content"})
        ws = self.sb.workspace("ws")
        site = self.sb.site("site", {"index.html": "old head content"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8, head_sequence=[HEAD, OTHER])
        self.assertEqual(rc, 0, log)
        self.assertEqual(out["state"], "superseded")
        self.assertNotIn("preview_ref", out)
        self.assertEqual(self.sb.remote_tip(), newer)
        self.assertEqual(self.sb.remote_file("pr-8/index.html"), "newer head content")

    def test_transport_failure_is_not_treated_as_missing_branch(self):
        ws = self.sb.workspace("ws")
        git("remote", "set-url", "origin", str(self.sb.root / "does-not-exist.git"), cwd=ws)
        site = self.sb.site("site", {"index.html": "PR 8"})
        rc, out, log = self.sb.run_publish(ws, site, pr=8)
        self.assertNotEqual(rc, 0)
        self.assertEqual(out.get("state"), "failed")
        self.assertIn("cannot read pages-previews from origin", log)
        self.assertNotIn("preview_ref", out)
        self.assertEqual(self.sb.remote_tip(), "refs/heads/pages-previews")  # branch never created

    def test_identical_content_still_publishes_a_commit_owned_by_this_run(self):
        site = self.sb.site("site", {"index.html": "same"})
        rc, first, log = self.sb.run_publish(self.sb.workspace("ws1"), site, pr=8)
        self.assertEqual(rc, 0, log)
        rc, second, log = self.sb.run_publish(self.sb.workspace("ws2"), site, pr=8)
        self.assertEqual(rc, 0, log)
        self.assertNotEqual(first["preview_ref"], second["preview_ref"])
        parent = git("rev-parse", f"{second['preview_ref']}^", cwd=self.sb.origin)
        self.assertEqual(parent, first["preview_ref"])
        message = git("log", "-1", "--format=%B", second["preview_ref"], cwd=self.sb.origin)
        self.assertIn("preview: PR #8 at " + HEAD, message)
        self.assertEqual(self.sb.remote_file("pr-8/index.html", second["preview_ref"]), "same")

    def test_parallel_writers_all_land(self):
        sites = {pr: self.sb.site(f"site{pr}", {"index.html": f"PR {pr}"}) for pr in (11, 12, 13, 14)}
        workspaces = {pr: self.sb.workspace(f"ws{pr}") for pr in sites}
        script = self.sb.root / "publish.sh"
        script.write_text(PUBLISH_SCRIPT)
        procs = []
        for pr, ws in workspaces.items():
            output = self.sb.root / f"par-{pr}.txt"
            output.write_text("")
            env = {**os.environ, "PATH": f"{self.sb.bin}{os.pathsep}{os.environ['PATH']}", "FAKE_PR_HEAD": HEAD,
                   "GITHUB_OUTPUT": str(output), "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": str(pr),
                   "PR_NUMBER": str(pr), "HEAD_SHA": HEAD, "PREVIEW_BRANCH": "pages-previews",
                   "PREVIEW_SITE": str(sites[pr]), "PREVIEW_MAX_ATTEMPTS": "10", "PREVIEW_BACKOFF_SECONDS": "1"}
            procs.append(subprocess.Popen(["bash", str(script)], cwd=ws, env=env,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
        logs = [proc.communicate(timeout=180)[0] for proc in procs]
        self.assertTrue(all(proc.returncode == 0 for proc in procs), logs)
        for pr in sites:
            self.assertEqual(self.sb.remote_file(f"pr-{pr}/index.html"), f"PR {pr}")


class WorkflowContractTests(unittest.TestCase):
    def test_no_force_push_and_no_single_shot_action(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("peaceiris/actions-gh-pages", text)
        self.assertNotIn("--force", PUBLISH_SCRIPT.replace("worktree remove --force", ""))
        self.assertNotRegex(PUBLISH_SCRIPT, r"git push[^\n]*\s(-f|\+)")

    def test_url_uses_exact_pushed_ref_and_later_steps_are_gated(self):
        url = _step("Resolve immutable preview URL")
        self.assertEqual(url["if"], "steps.publish.outputs.state == 'published'")
        self.assertIn("steps.publish.outputs.preview_ref", url["env"]["PREVIEW_REF"])
        self.assertNotIn("ls-remote", url["run"])
        self.assertEqual(_step("Verify browser preview")["if"], "steps.publish.outputs.state == 'published'")
        record = _step("Record preview result")["with"]["script"]
        self.assertIn("superseded", record)
        # Live head re-check before mutating the shared marker comment.
        self.assertIn("github.rest.pulls.get", record)
        self.assertLess(record.index("livePr.head.sha !== process.env.HEAD_SHA"), record.index("updateComment"))

    def test_head_is_rechecked_right_before_push(self):
        before_push = PUBLISH_SCRIPT.split('if git push origin "${candidate}', 1)[0]
        code_lines = [line.strip() for line in before_push.splitlines()
                      if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(code_lines[-1], "superseded_if_head_moved")
        self.assertIn("Residual TOCTOU", WORKFLOW.read_text(encoding="utf-8"))

    def test_permissions_fork_guard_and_triggers_are_unchanged(self):
        wf = _workflow()
        preview = wf["jobs"]["preview"]
        self.assertEqual(preview["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", preview["if"])
        self.assertEqual(wf["permissions"], {"contents": "read", "pages": "write", "id-token": "write"})
        self.assertNotIn("pull_request_target", wf[True] if True in wf else wf["on"])


if __name__ == "__main__":
    unittest.main()
