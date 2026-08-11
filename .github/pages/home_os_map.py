from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


KNOWN_ROUTES = {
    "/reports/morning/",
    "/decision-cockpit/daihen/",
    "/risk-preflight/",
    "/research/market-phase/ai-semiconductor/",
    "/companies/",
    "/framework/",
    "/trade-journal/",
    "/trade-analysis/",
    "/market-analysis/",
}

VALID_AVAILABILITY = {"AVAILABLE", "UNAVAILABLE", "UNMAPPED"}


def load_os_map(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_os_map(payload)
    return payload


def validate_os_map(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported OS map schema_version")

    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != 9:
        raise ValueError("OS map must contain exactly 9 stages")

    required = {
        "stage_id",
        "purpose_ja",
        "description_ja",
        "representative_ja",
        "primary_destination",
        "availability",
    }
    seen_ids: set[str] = set()
    for stage in stages:
        missing = required - set(stage)
        if missing:
            raise ValueError(f"OS map stage missing fields: {sorted(missing)}")
        stage_id = stage["stage_id"]
        if stage_id in seen_ids:
            raise ValueError(f"duplicate stage_id: {stage_id}")
        seen_ids.add(stage_id)
        _validate_destination(stage["primary_destination"], stage["availability"])

    today_entries = payload.get("today_entries")
    if not isinstance(today_entries, list) or not today_entries:
        raise ValueError("today_entries must not be empty")
    for entry in today_entries:
        for field in ("label_ja", "description_ja", "route", "availability"):
            if field not in entry:
                raise ValueError(f"today entry missing field: {field}")
        _validate_destination(entry["route"], entry["availability"])


def _validate_destination(route: str | None, availability: str) -> None:
    if availability not in VALID_AVAILABILITY:
        raise ValueError(f"invalid availability: {availability}")
    if availability == "AVAILABLE":
        if not route or route not in KNOWN_ROUTES:
            raise ValueError(f"AVAILABLE destination is not in route inventory: {route}")
        return
    if route:
        raise ValueError("UNAVAILABLE / UNMAPPED destination must not invent a route")


def _relative_link(
    route: str,
    label: str,
    class_name: str,
    *,
    accessible_name: str | None = None,
) -> str:
    escaped_label = html.escape(label)
    escaped_route = html.escape(route, quote=True)
    aria = (
        f' aria-label="{html.escape(accessible_name, quote=True)}"'
        if accessible_name
        else ""
    )
    return (
        f'<a class="{class_name}"{aria} '
        f'href="{{{{ \'{escaped_route}\' | relative_url }}}}">{escaped_label}</a>'
    )


def render_today(entries: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for entry in entries:
        state = entry["availability"].lower()
        raw_label = str(entry["label_ja"])
        label = html.escape(raw_label)
        description = html.escape(entry["description_ja"])
        if entry["availability"] == "AVAILABLE":
            action = _relative_link(
                entry["route"],
                "開く",
                "codex-action codex-action--primary",
                accessible_name=f"{raw_label}を開く",
            )
            state_label = "利用可能"
            state_token = "normal"
        else:
            action = '<span class="home-os-caption">この入口では現在取得できません</span>'
            state_label = "利用不可"
            state_token = "unavailable"
        cards.append(
            '<article class="codex-summary-card home-priority-first" '
            f'data-availability="{state}">'
            f'<span class="codex-status-chip" data-state="{state_token}">{state_label}</span>'
            f'<h3>{label}</h3><p>{description}</p>{action}</article>'
        )
    return '<div class="codex-summary-grid home-today-grid">\n' + "\n".join(cards) + "\n</div>"


def render_stages(stages: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for index, stage in enumerate(stages, start=1):
        availability = stage["availability"]
        purpose = html.escape(stage["purpose_ja"])
        description = html.escape(stage["description_ja"])
        representative = html.escape(stage["representative_ja"])
        if availability == "AVAILABLE":
            action = _relative_link(
                stage["primary_destination"],
                representative,
                "codex-action codex-action--secondary",
            )
            status = '<span class="codex-status-chip" data-state="normal">利用可能</span>'
        else:
            action = '<span class="home-os-caption">接続先は未設定です</span>'
            status = '<span class="codex-status-chip" data-state="unavailable">利用不可</span>'
        cards.append(
            '<article class="codex-summary-card home-os-stage" '
            f'data-stage-id="{html.escape(stage["stage_id"], quote=True)}">'
            f'<div class="home-os-stage__number" aria-hidden="true">{index:02d}</div>'
            f'<div><div class="home-os-stage__header"><h3>{purpose}</h3>{status}</div>'
            f'<p>{description}</p>{action}</div></article>'
        )
    return '<div class="home-os-map" aria-label="Investment OS 9段階">\n' + "\n".join(cards) + "\n</div>"


def render_home(template: str, payload: dict[str, Any]) -> str:
    validate_os_map(payload)
    replacements = {
        "<!-- SIL:TODAY_ENTRIES -->": render_today(payload["today_entries"]),
        "<!-- SIL:OS_LOOP_LABEL -->": html.escape(payload["loop_label_ja"]),
        "<!-- SIL:OS_MAP_STAGES -->": render_stages(payload["stages"]),
    }
    output = template
    for marker, rendered in replacements.items():
        if marker not in output:
            raise ValueError(f"Home template marker missing: {marker}")
        output = output.replace(marker, rendered)
    return output
