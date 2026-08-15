from scripts.review_routing_policy import (
    classify_blocking_gates,
    evaluate_gate_carry_forward,
    evaluate_review_wait_sla,
)


def test_backend_only_requires_one_technical_gate():
    result = classify_blocking_gates({"change_surfaces": ["backend"]})
    assert result["status"] == "ROUTED"
    assert result["blocking_gates"] == ("TECHNICAL",)
    assert result["blocking_gate_count"] == 1
    assert result["default_limit_exceeded"] is False


def test_process_flow_requires_one_flow_technical_gate():
    result = classify_blocking_gates({"change_surfaces": ["process_flow"]})
    assert result["blocking_gates"] == ("TECHNICAL_FLOW",)
    assert result["blocking_gate_count"] == 1


def test_ui_requires_technical_and_design_only():
    result = classify_blocking_gates({"change_surfaces": ["ui_visual"]})
    assert result["blocking_gates"] == ("TECHNICAL", "DESIGN")
    assert result["blocking_gate_count"] == 2
    assert "RESEARCH" in result["non_blocking_specialists"]
    assert "PRODUCT" in result["non_blocking_specialists"]


def test_research_truth_requires_technical_and_research():
    result = classify_blocking_gates({"change_surfaces": ["research_truth"]})
    assert result["blocking_gates"] == ("TECHNICAL", "RESEARCH")


def test_product_semantics_requires_product_but_not_research_when_truth_unchanged():
    result = classify_blocking_gates(
        {"change_surfaces": ["product_semantics"], "market_truth_changed": False}
    )
    assert result["blocking_gates"] == ("TECHNICAL", "PRODUCT")
    assert "RESEARCH" in result["non_blocking_specialists"]


def test_product_plus_market_truth_keeps_required_third_gate_as_explicit_exception():
    result = classify_blocking_gates(
        {"change_surfaces": ["product_semantics"], "market_truth_changed": True}
    )
    assert result["blocking_gates"] == ("TECHNICAL", "PRODUCT", "RESEARCH")
    assert result["default_limit_exceeded"] is True
    assert "PRODUCT_AND_RESEARCH_TRUTH_COMBINED" in result["limit_exception_reasons"]


def test_workflow_security_requires_technical_and_security_flow():
    result = classify_blocking_gates({"change_surfaces": ["workflow_security"]})
    assert result["blocking_gates"] == ("TECHNICAL", "SECURITY_FLOW")


def test_docs_nonsemantic_requires_one_relevant_reviewer():
    result = classify_blocking_gates({"change_surfaces": ["docs_nonsemantic"]})
    assert result["blocking_gates"] == ("RELEVANT_SPECIALIST",)


def test_unknown_or_missing_surface_fails_closed():
    unknown = classify_blocking_gates({"change_surfaces": ["magic"]})
    missing = classify_blocking_gates({"change_surfaces": []})
    assert unknown["status"] == "UNKNOWN"
    assert unknown["blocking_gate_count"] is None
    assert missing["status"] == "UNKNOWN"


def test_owner_authority_is_never_removed_for_gate_count_limit():
    result = classify_blocking_gates(
        {"change_surfaces": ["product_semantics"], "owner_authority_required": True}
    )
    assert "OWNER_AUTHORITY" in result["blocking_gates"]
    assert result["blocking_gate_count"] == 3
    assert "OWNER_AUTHORITY_REQUIRED" in result["limit_exception_reasons"]


def test_unaffected_passed_gate_can_carry_forward():
    result = evaluate_gate_carry_forward(
        gate="DESIGN",
        gate_surfaces=["ui_visual"],
        changed_surfaces=["backend"],
        prior_status="PASS",
        prior_evidence_known=True,
    )
    assert result["decision"] == "CARRY_FORWARD"


def test_affected_or_unknown_gate_must_be_rereviewed():
    affected = evaluate_gate_carry_forward(
        gate="DESIGN",
        gate_surfaces=["ui_visual"],
        changed_surfaces=["ui_visual"],
        prior_status="PASS",
        prior_evidence_known=True,
    )
    unknown = evaluate_gate_carry_forward(
        gate="DESIGN",
        gate_surfaces=["ui_visual"],
        changed_surfaces=[],
        prior_status="PASS",
        prior_evidence_known=True,
    )
    prior_unknown = evaluate_gate_carry_forward(
        gate="DESIGN",
        gate_surfaces=["ui_visual"],
        changed_surfaces=["backend"],
        prior_status="PASS",
        prior_evidence_known=False,
    )
    assert affected["decision"] == "RE_REVIEW"
    assert unknown["decision"] == "RE_REVIEW"
    assert prior_unknown["decision"] == "RE_REVIEW"


def test_primary_review_sla_reroutes_after_60_minutes():
    result = evaluate_review_wait_sla(
        blocking=True,
        reviewer_kind="PRIMARY",
        wait_age_minutes=60,
        alternate_available=True,
    )
    assert result["status"] == "SLA_EXCEEDED"
    assert result["action"] == "REROUTE_REVIEW"
    assert result["target_minutes"] == 60


def test_specialist_review_sla_reroutes_after_120_minutes():
    result = evaluate_review_wait_sla(
        blocking=True,
        reviewer_kind="SPECIALIST",
        wait_age_minutes=120,
        alternate_available=True,
    )
    assert result["action"] == "REROUTE_REVIEW"
    assert result["target_minutes"] == 120


def test_required_gate_without_alternate_blocked_escapes_instead_of_dropping_gate():
    result = evaluate_review_wait_sla(
        blocking=True,
        reviewer_kind="SPECIALIST",
        wait_age_minutes=150,
        alternate_available=False,
    )
    assert result["status"] == "SLA_EXCEEDED"
    assert result["action"] == "BLOCKED_ESCAPE_KEEP_REQUIRED_GATE"


def test_unknown_wait_age_and_reviewer_kind_fail_closed():
    missing_age = evaluate_review_wait_sla(
        blocking=True,
        reviewer_kind="PRIMARY",
        wait_age_minutes=None,
        alternate_available=True,
    )
    unknown_kind = evaluate_review_wait_sla(
        blocking=True,
        reviewer_kind="MYSTERY",
        wait_age_minutes=10,
        alternate_available=True,
    )
    assert missing_age["status"] == "UNKNOWN"
    assert missing_age["action"] == "COLLECT_WAIT_AGE"
    assert unknown_kind["status"] == "UNKNOWN"
    assert unknown_kind["action"] == "FAIL_CLOSED"
