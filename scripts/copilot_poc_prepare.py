from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


FORBIDDEN_ISSUE = 79
READY_MARKERS = ("READY_FOR_IMPLEMENTATION", "READY_FOR_POC")
AUTONOMY_ISSUE = 431


def _github_get(path: str, token: str) -> object:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sado-investment-lab-copilot-poc",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _extract_sections(text: str) -> str:
    """Keep the issue contract readable while avoiding an unbounded prompt."""
    headings = ("Goal", "Scope", "Acceptance", "Acceptance Criteria", "Non-goal", "Non-goals")
    lines = text.splitlines()
    selected: list[str] = []
    active = False
    for line in lines:
        heading = re.match(r"^#{1,4}\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(1).strip()
            active = any(title.lower().startswith(item.lower()) for item in headings)
        if active:
            selected.append(line)
    return "\n".join(selected).strip() or text[:12000]


def _latest_ready_comment(comments: list[dict]) -> str:
    ready = []
    for comment in comments:
        body = str(comment.get("body") or "")
        if any(marker in body for marker in READY_MARKERS):
            ready.append(body)
    return ready[-1] if ready else ""


def prepare(repo: str, issue_number: int, token: str, output: Path) -> None:
    if issue_number == FORBIDDEN_ISSUE:
        raise ValueError("Issue #79 is permanently forbidden for this PoC")
    if issue_number <= 0:
        raise ValueError("issue_number must be positive")

    owner, name = repo.split("/", 1)
    issue = _github_get(f"/repos/{owner}/{name}/issues/{issue_number}", token)
    if not isinstance(issue, dict) or "pull_request" in issue:
        raise ValueError("target must be a GitHub Issue, not a pull request")
    if issue.get("state") != "open":
        raise ValueError("target issue must be open")

    comments = _github_get(f"/repos/{owner}/{name}/issues/{issue_number}/comments?per_page=100", token)
    if not isinstance(comments, list):
        raise ValueError("could not load issue comments")

    body = str(issue.get("body") or "")
    ready_comment = _latest_ready_comment(comments)
    combined = body + "\n" + ready_comment
    if not any(marker in combined for marker in READY_MARKERS):
        raise ValueError("target issue is not explicitly READY_FOR_IMPLEMENTATION/READY_FOR_POC")

    autonomy = _github_get(f"/repos/{owner}/{name}/issues/{AUTONOMY_ISSUE}", token)
    autonomy_body = str(autonomy.get("body") or "") if isinstance(autonomy, dict) else ""
    team_rules = Path("TEAM_RULES.md").read_text(encoding="utf-8")

    prompt = f"""You are running the Sado Investment Lab Copilot PoC1 in an isolated GitHub Actions worktree.

TARGET ISSUE: #{issue_number} — {issue.get('title', '')}

HARD BOUNDARIES:
- Work only inside the target Issue Goal/Scope/Acceptance Criteria/Non-goals.
- Issue #79 must never be touched.
- Do not modify .github/workflows, dependency manifests, lockfiles, TEAM_RULES.md, TEAM_STATE.md, secrets, permissions, billing, or canonical investment state.
- Do not run git commit, git push, gh write operations, destructive delete/history rewrite, merge, or issue close.
- Do not infer BUY/SELL/HOLD, risk thresholds, Owner Authority, or missing canonical facts.
- Do not ask a user a question. If blocked, stop safely and write why to copilot-poc-result.md.
- You may inspect the repository, edit ordinary worktree files within scope, and run existing tests/lint/build commands.
- Finish by writing copilot-poc-result.md with OUTCOME, CHANGED_FILES, TESTS, BLOCKED_REASON, CONFIRMATION_COUNT=0.

TARGET ISSUE CONTRACT:
{_extract_sections(body)}

LATEST READY HANDOFF:
{ready_comment[:10000]}

AI IMPLEMENTATION AUTONOMY POLICY (#431 excerpt):
{_extract_sections(autonomy_body)[:10000]}

TEAM_RULES.md is authoritative and already present in the worktree. Relevant operating constraint: follow its repository change and authority boundaries. Do not weaken them.
"""
    output.write_text(prompt, encoding="utf-8")


def main() -> int:
    try:
        repo = os.environ["GITHUB_REPOSITORY"]
        token = os.environ["GITHUB_TOKEN"]
        issue_number = int(os.environ["ISSUE_NUMBER"])
        prepare(repo, issue_number, token, Path("copilot-poc-prompt.md"))
        return 0
    except (KeyError, ValueError, urllib.error.URLError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        Path("copilot-poc-blocked.txt").write_text(str(exc), encoding="utf-8")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
