#!/usr/bin/env python3
"""Read-only Pages UX evidence preflight. Not an AI or investor recommendation."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date
from pathlib import Path


def finding(rule: str, severity: str, route: str, evidence: str, recommendation: str) -> dict:
    return {"rule": rule, "severity": severity, "route": route,
            "evidence": evidence, "recommendation": recommendation}


def inspect(root: Path) -> dict:
    findings = []
    manifest = {"source": "repository_artifact", "ai_review": "NOT_RUN",
                "browser_review": "NOT_RUN", "public_http_verified": False}
    dataset_file = root / "data/generated/public/morning-dataset.json"
    if not dataset_file.is_file():
        findings.append(finding("MORNING_DATA_MISSING", "P0", "/",
                                str(dataset_file.relative_to(root)), "生成済みDatasetの入力元を確認"))
    else:
        try:
            data = json.loads(dataset_file.read_text(encoding="utf-8"))
            manifest["morning_as_of"] = data.get("as_of")
            manifest["generated_at"] = data.get("generated_at")
            statuses = {x.get("name"): x for x in data.get("source_status", []) if isinstance(x, dict)}
            for name in ("portfolio", "capital", "events", "watchlist", "candidates"):
                row = statuses.get(name)
                if row is None:
                    findings.append(finding("SOURCE_STATUS_ABSENT", "P0", "/", name, "source_statusへ情報を記録"))
                elif row.get("status") != "OK":
                    findings.append(finding("SOURCE_NOT_CURRENT", "P1", "/",
                        f"{name}: {row.get('status')} as_of={row.get('as_of')} reason={row.get('reason')}",
                        "冒頭に確認日と未取得原因を表示し、今の投資判断に使わない"))
            candidates = data.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                reason = "missing" if "candidates" not in data else ("empty" if candidates == [] else "invalid")
                findings.append(finding("NO_VERIFIED_FOCUS", "P0", "/",
                    f"candidates {reason}",
                    "今日の検証済み注目銘柄は未確定（候補データなし／未取得）"))
            else:
                def valid_priority(item):
                    priority = item.get("total_priority")
                    return (isinstance(priority, (int, float)) and not isinstance(priority, bool)
                            and math.isfinite(priority))
                if not any(isinstance(item, dict) and item.get("status") == "OK"
                           and valid_priority(item) for item in candidates):
                    findings.append(finding("NO_VERIFIED_FOCUS", "P0", "/",
                        f"candidates={len(candidates)}; none with OK status and valid numeric priority",
                        "今日の検証済み注目候補は未確定と表示。過去の保有/Researchを新情報として昇格しない"))
        except (OSError, ValueError, TypeError, AttributeError) as ex:
            findings.append(finding("MORNING_DATA_UNREADABLE", "P0", "/",
                type(ex).__name__, "データ生成・JSON構造を確認。欠損を正常とみなさない"))
    cockpit_file = root / ".github/pages/build_daihen_cockpit.py"
    if not cockpit_file.is_file():
        findings.append(finding("DAIHEN_SOURCE_MISSING", "P0", "/decision-cockpit/daihen/",
                                "builder missing", "公開ルート生成器を確認"))
    else:
        try:
            source = cockpit_file.read_text(encoding="utf-8")
            # This is a source heuristic; a browser review must establish actual UX.
            # Only extract the teaser function, not unrelated page sections or links.
            match = re.search(r"^def _expectation_first_view\(.*?(?=^def |^class |\Z)",
                              source, flags=re.S | re.M)
            teaser = match.group(0) if match else ""
            if "cockpit-expectation-summary" in teaser:
                # A link anywhere else in this function is not proof that the teaser navigates.
                # Only treat an anchor inside the teaser itself as a source-level indication;
                # actual target existence and click behavior still require browser validation.
                card = re.search(r"<(?:div|a)[^>]*cockpit-expectation-summary[^>]*>.*?</(?:div|a)>",
                                 teaser, flags=re.S)
                has_card_anchor = bool(card and re.search(r"<a\s+[^>]*href=[\\\"']#market-expectations[\\\"']",
                                                          card.group(0)))
                if not has_card_anchor:
                    findings.append(finding("DEAD_EXPECTATION_TEASER", "P1",
                        "/decision-cockpit/daihen/", "teaser has no verified local market-expectations anchor; browser NOT_RUN",
                        "市場期待比較への実際に動作するアンカーリンクを設け、ブラウザで確認する"))
            if "company-research:6622" in source or "### Must happen" in source:
                findings.append(finding("DEVELOPER_VOCABULARY_REVIEW", "P2",
                    "/decision-cockpit/daihen/", "technical references/English labels in builder",
                    "日本語の投資判断文を上位に置き、参照IDは詳細へ"))
        except (OSError, UnicodeError) as ex:
            findings.append(finding("DAIHEN_SOURCE_UNREADABLE", "P0", "/decision-cockpit/daihen/",
                type(ex).__name__, "生成器の読み込みを確認。未検証を正常とみなさない"))
    return {"schema_version": 1, "review_as_of": date.today().isoformat(),
            "run_scope": manifest, "findings": findings, "finding_count": len(findings),
            "result": "FINDINGS" if findings else "NO_STATIC_FINDINGS_AI_NOT_RUN"}


def render_markdown(report: dict) -> str:
    result = ["# Pages 読み取り専用レビュー — 静的前提検査", "",
              f"Review: {report['review_as_of']}",
              "**AIによる意味理解レビュー／ブラウザ表示検証／公開HTTP検証は未実施。**",
              "このレポートが空でもUX合格を意味しません。", "",
              f"静的指摘: {report['finding_count']}件", ""]
    for item in report["findings"]:
        result += [f"## {item['severity']} {item['rule']}",
                   f"- 対象: `{item['route']}`",
                   f"- 根拠: {item['evidence']}",
                   f"- 対応案: {item['recommendation']}", ""]
    return "\n".join(result) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("pages-review"))
    args = parser.parse_args()
    report = inspect(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "review.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"result": report["result"], "findings": report["finding_count"],
                      "ai_review": "NOT_RUN"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
