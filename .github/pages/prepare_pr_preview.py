#!/usr/bin/env python3
"""Prepare a built Pages artifact for an isolated pull-request preview."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


BANNER_ID = "sado-pr-preview-banner"


def preview_prefix(owner: str, repo: str, ref: str, namespace: str) -> str:
    return f"/{owner}/{repo}/{ref}/{namespace}/"


def rewrite_html(
    html: str,
    *,
    production_base: str,
    prefix: str,
    pr_number: int,
    head_sha: str,
    built_at: str,
) -> str:
    """Rewrite production-root links and add an unmistakable preview banner."""
    production_base = "/" + production_base.strip("/") + "/"
    production_root = production_base.rstrip("/")
    html = re.sub(
        rf'(?P<quote>["\']){re.escape(production_root)}(?P=quote)',
        lambda match: f"{match.group('quote')}{prefix.rstrip('/')}{match.group('quote')}",
        html,
    )
    html = html.replace(production_base, prefix)

    # raw.githack serves files rather than GitHub Pages-style directory indexes.
    # Make internal directory links explicit while leaving assets and externals alone.
    escaped_prefix = re.escape(prefix)
    html = re.sub(
        rf'(?P<attr>href=["\'])({escaped_prefix})(?P<path>[^"\'#?]*?)/(?P<tail>[#?][^"\']*)?(?P<quote>["\'])',
        lambda match: (
            f"{match.group('attr')}{match.group(2)}{match.group('path')}/index.html"
            f"{match.group('tail') or ''}{match.group('quote')}"
        ),
        html,
    )

    if BANNER_ID in html:
        return html

    short_sha = head_sha[:12]
    banner = f'''\n<div id="{BANNER_ID}" role="status" aria-label="Pull request preview">
  <strong>PR PREVIEW · #{pr_number} · NOT PRODUCTION</strong>
  <span>Head {short_sha} · Built {built_at}</span>
</div>
<style>
  #{BANNER_ID} {{
    box-sizing: border-box; position: relative; z-index: 2147483647;
    display: flex; flex-wrap: wrap; justify-content: center; gap: .4rem 1rem;
    width: 100%; padding: .55rem 1rem; color: #fff; background: #8b1e2d;
    font: 600 .82rem/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    text-align: center;
  }}
  #{BANNER_ID} span {{ font-weight: 400; overflow-wrap: anywhere; }}
  @media (max-width: 640px) {{ #{BANNER_ID} {{ align-items: center; flex-direction: column; gap: .15rem; }} }}
</style>\n'''
    body_match = re.search(r"<body(?:\s[^>]*)?>", html, flags=re.IGNORECASE)
    if body_match:
        return html[: body_match.end()] + banner + html[body_match.end() :]
    return banner + html


def prepare_preview(
    root: Path,
    *,
    owner: str,
    repo: str,
    ref: str,
    namespace: str,
    pr_number: int,
    head_sha: str,
    built_at: str,
) -> dict[str, object]:
    if not root.is_dir():
        raise ValueError(f"Preview root does not exist: {root}")
    if not (root / "index.html").is_file():
        raise ValueError(f"Preview root has no index.html: {root}")

    prefix = preview_prefix(owner, repo, ref, namespace)
    production_base = f"/{repo}/"
    html_files = sorted(root.rglob("*.html"))
    for path in html_files:
        original = path.read_text(encoding="utf-8")
        path.write_text(
            rewrite_html(
                original,
                production_base=production_base,
                prefix=prefix,
                pr_number=pr_number,
                head_sha=head_sha,
                built_at=built_at,
            ),
            encoding="utf-8",
        )

    metadata: dict[str, object] = {
        "schema_version": "1.0",
        "preview": True,
        "not_production": True,
        "pull_request": pr_number,
        "head_sha": head_sha,
        "built_at": built_at,
        "namespace": namespace,
        "html_files": len(html_files),
    }
    (root / "preview-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", default="pages-previews")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument(
        "--built-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args()
    metadata = prepare_preview(
        args.root,
        owner=args.owner,
        repo=args.repo,
        ref=args.ref,
        namespace=args.namespace,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        built_at=args.built_at,
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
