#!/usr/bin/env python3
"""Prepare a built Pages artifact for an isolated pull-request preview."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


BANNER_ID = "sado-pr-preview-banner"


_URL_ATTRIBUTES = frozenset({"href", "src"})


def _tag_end(source: str, start: int) -> int | None:
    """Return the closing > while respecting quoted attribute values."""
    quote: str | None = None
    index = start
    while index < len(source):
        char = source[index]
        if quote:
            if char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == ">":
            return index
        index += 1
    return None


def _rewrite_preview_url(value: str, *, production_base: str, prefix: str) -> str:
    production_root = production_base.rstrip("/")
    if value == production_root:
        return prefix.rstrip("/")
    if not value.startswith(production_base):
        return value

    rewritten = prefix + value[len(production_base):]
    match = re.match(r"([^?#]*)(.*)", rewritten)
    assert match is not None
    path, tail = match.groups()
    if path.endswith("/"):
        path += "index.html"
    return path + tail


def _rewrite_start_tag(tag: str, *, production_base: str, prefix: str) -> str:
    """Rewrite only real href/src value spans and preserve all other source bytes."""
    if not tag.startswith("<") or tag.startswith(("</", "<!", "<?")):
        return tag

    index = 1
    while index < len(tag) and not tag[index].isspace() and tag[index] not in "/>":
        index += 1

    replacements: list[tuple[int, int, str]] = []
    while index < len(tag):
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] in "/>":
            break

        name_start = index
        while index < len(tag) and not tag[index].isspace() and tag[index] not in "=/>":
            index += 1
        name = tag[name_start:index].lower()
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] != "=":
            continue

        index += 1
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag):
            break

        if tag[index] in {'"', "'"}:
            quote = tag[index]
            value_start = index + 1
            value_end = tag.find(quote, value_start)
            if value_end < 0:
                return tag
            index = value_end + 1
        else:
            value_start = index
            while index < len(tag) and not tag[index].isspace() and tag[index] != ">":
                index += 1
            value_end = index

        if name in _URL_ATTRIBUTES:
            value = tag[value_start:value_end]
            rewritten = _rewrite_preview_url(
                value,
                production_base=production_base,
                prefix=prefix,
            )
            if rewritten != value:
                replacements.append((value_start, value_end, rewritten))

    for start, end, value in reversed(replacements):
        tag = tag[:start] + value + tag[end:]
    return tag


def _rewrite_url_attributes(html: str, *, production_base: str, prefix: str) -> str:
    """Rewrite root-relative URL attributes without touching text, scripts, or externals."""
    output: list[str] = []
    position = 0
    raw_text: str | None = None

    while position < len(html):
        if raw_text:
            closing = re.search(rf"</{raw_text}\\s*>", html[position:], re.IGNORECASE)
            if not closing:
                output.append(html[position:])
                break
            end = position + closing.end()
            output.append(html[position:end])
            position = end
            raw_text = None
            continue

        tag_start = html.find("<", position)
        if tag_start < 0:
            output.append(html[position:])
            break
        output.append(html[position:tag_start])

        if html.startswith("<!--", tag_start):
            comment_end = html.find("-->", tag_start + 4)
            if comment_end < 0:
                output.append(html[tag_start:])
                break
            end = comment_end + 3
            output.append(html[tag_start:end])
            position = end
            continue

        tag_end = _tag_end(html, tag_start + 1)
        if tag_end is None:
            output.append(html[tag_start:])
            break

        tag = html[tag_start:tag_end + 1]
        output.append(
            _rewrite_start_tag(
                tag,
                production_base=production_base,
                prefix=prefix,
            )
        )
        position = tag_end + 1

        opening = re.match(r"<\\s*(script|style)(?:\\s|>)", tag, re.IGNORECASE)
        if opening and not tag.rstrip().endswith("/>"):
            raw_text = opening.group(1)

    return "".join(output)


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
    html = _rewrite_url_attributes(
        html,
        production_base=production_base,
        prefix=prefix,
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
