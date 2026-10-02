from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONSUMER=ROOT/".github/workflows/queue-auto-promotion-consumer.yml"
DISPATCH=ROOT/".github/workflows/ai-production-dispatch.yml"
def _read(path): return path.read_text(encoding="utf-8")
def test_triggers(): t=_read(CONSUMER); assert "schedule:" in t and "cron:" in t and "workflow_dispatch:" in t
def test_never_79(): t=_read(CONSUMER); assert ".number != 79" in t and '[[ "$ISSUE_NUMBER" != "79" ]]' in t and "PROTECTED_ISSUE_79" in t
def test_bounded_scan(): t=_read(CONSUMER); assert "READY_FOR_IMPLEMENTATION" in t and "per_page=20" in t and '(.pull_request // null) == null' in t
def test_reuses_adapter(): t=_read(CONSUMER); assert "scripts/queue_auto_promotion_consumer.py" in t and "--active-owner-slices" in t and "--active-paths" in t
def test_duplicate_lease_guard(): t=_read(CONSUMER); assert "AUTO_ROUTER_DISPATCH lease_id=.* executor=COPILOT target_issue=" in t and "duplicate-active-lease fail-closed" in t
def test_conflicting_pr_paths(): t=_read(CONSUMER); assert "pulls?state=open" in t and "/files?per_page=100" in t and "--active-paths /tmp/active-paths.json" in t
def test_one_lease_and_canonical_dispatch():
    t=_read(CONSUMER); d=_read(DISPATCH); assert "DISPATCH_READY" in t and "gh workflow run ai-production-dispatch.yml" in t and '-f issue_number="$ISSUE_NUMBER"' in t and '-f lease_id="$LEASE_ID"' in t and '^lease-[0-9a-f]{32}$' in d and '^lease-[0-9a-f]{32}$' in t
def test_fail_closed(): t=_read(CONSUMER); assert "No safe candidate this tick" in t and "No executor dispatch this tick (fail-closed)" in t
def test_no_duplicate_fallback_policy(): t=_read(CONSUMER); assert ("quota" not in t.lower() or "provider health are owned by the existing" in t) and "amazon_q_free" not in t and "ai-production-followup.yml" not in t
def test_attributed_evidence(): t=_read(CONSUMER); assert "担当: 🌊ナギ" in t and "種別:" in t and "-F body=@/tmp/evidence-comment.md" in t
def test_no_merge_or_team_docs(): t=_read(CONSUMER); assert "gh pr merge" not in t and "enable-auto-merge" not in t and "TEAM_RULES.md" not in t and "TEAM_STATE.md" not in t
