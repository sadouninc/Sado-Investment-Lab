from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedRef:
    ref: str
    href: str | None
    kind: str
    label: str


DAIHEN_RESEARCH_ROUTE = "/companies/infrastructure/6622-daihen/"
GITHUB_ISSUE_BASE = "https://github.com/sadouninc/Sado-Investment-Lab/issues/"


def resolve_cockpit_ref(ref: object) -> ResolvedRef:
    """Resolve only explicit, known-stable destinations.

    Unknown canonical refs stay unresolved rather than guessing a route.
    """
    text = str(ref or "").strip()
    if not text:
        return ResolvedRef(ref=text, href=None, kind="EMPTY", label="参照なし")

    if text.startswith("issue:"):
        number = text.split(":", 1)[1]
        if number.isdigit() and int(number) > 0:
            return ResolvedRef(
                ref=text,
                href=f"{GITHUB_ISSUE_BASE}{number}",
                kind="GITHUB_ISSUE",
                label=f"Issue #{number}",
            )
        return ResolvedRef(ref=text, href=None, kind="INVALID", label="不正なIssue参照")

    if text.startswith("company-research:6622:"):
        return ResolvedRef(
            ref=text,
            href=DAIHEN_RESEARCH_ROUTE,
            kind="COMPANY_RESEARCH",
            label="ダイヘン企業研究",
        )

    known_unrouted_prefixes = (
        "forward-per:6622:",
        "hypothesis:6622:",
        "decision:6622:",
        "decision-snapshot:6622:",
        "decision-comparison:6622:",
        "episode:6622:",
    )
    if text.startswith(known_unrouted_prefixes):
        return ResolvedRef(
            ref=text,
            href=None,
            kind="CANONICAL_UNROUTED",
            label="専用ページ未生成",
        )

    return ResolvedRef(ref=text, href=None, kind="UNKNOWN", label="リンク先未定義")


def first_resolved_href(refs: object) -> str | None:
    for ref in list(refs or []):
        resolved = resolve_cockpit_ref(ref)
        if resolved.href:
            return resolved.href
    return None
