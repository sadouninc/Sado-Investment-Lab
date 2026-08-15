from scripts.review_routing_policy import (
    DESIGN,
    PRODUCT,
    RESEARCH,
    SECURITY_FLOW,
    TECHNICAL,
    carry_forward_gate,
    review_wait_action,
    route_reviews,
)


def test_process_flow_requires_only_technical_blocking_gate():
    result = route_reviews(
        {
            "changed_paths": ["scripts/flow_control_loop.py", "tests/test_flow_control_loop.py"],
            "semantic_surface": "queue routing process",
        }
    )
    assert result["status"] == "ROUTED"
    assert result["category"] == "PROCESS_FLOW"
    assert result["blocking_gates"] == (TECHNICAL,)
    assert DESIGN in result["non_blocking_gates"]
    assert RESEARCH in result["non_blocking_gates"]
    assert PRODUCT in result["non_blocking_gates"]


def test_ui_visual_requires_technical_and_design():
    result = route_reviews(
        {
            "changed_paths": ["docs/cockpit/index.html"],
            "ui_visual_change": True,
        }
    )
    assert result["blocking_gates"] == (TECHNICAL, DESIGN)
    assert result["blocking_gate_count"] == 2


def test_market_truth_requires_technical_and_research():
    result = route_reviews(
        {"changed_paths": ["scripts/market_price_identity.py"]}
    )
    assert result["blocking_gates"] == (TECHNICAL, RESEARCH)


def test_security_workflow_requires_technical_and_security_flow():
    result = route_reviews(
        {"changed_paths": [".github/workflows/ai-production-dispatch.yml"]}
    )
    assert result["blocking_gates"] == (TECHNICAL, SECURITY_FLOW)
    assert result["blocking_gate_count"] == 2


def test_unknown_surface_fails_closed():
    result = route_reviews({"changed_paths": []})
    assert result["status"] == "BLOCK"
    assert result["reason"] == "UNKNOWN_REVIEW_SURFACE"


def test_default_routes_never_exceed_two_blocking_gates():
    fixtures = [
        {"category": "BACKEND"},
        {"category": "PROCESS_FLOW"},
        {"category": "UI_VISUAL"},
        {"category": "MARKET_RESEARCH_TRUTH"},
        {"category": "PRODUCT_SEMANTICS"},
        {"category": "SECURITY_WORKFLOW"},
        {"category": "DOCS_ONLY"},
    ]
    for fixture in fixtures:
        result = route_reviews(fixture)
        assert result["blocking_gate_count"] <= 2


def test_product_and_market_truth_cross_authority_is_explicit_exception():
    result = route_reviews(
        {"category": "PRODUCT_SEMANTICS", "market_truth_changed": True}
    )
    assert result["blocking_gates"] == (TECHNICAL, PRODUCT, RESEARCH)


def test_truthy_string_does_not_enable_cross_authority_exception():
    result = route_reviews(
        {"category": "PRODUCT_SEMANTICS", "market_truth_changed": "false"}
    )
    assert result["blocking_gates"] == (TECHNICAL, PRODUCT)
    assert result["blocking_gate_count"] == 2


def test_unaffected_previous_gate_can_carry_forward():
    result = carry_forward_gate(
        gate=DESIGN,
        previous_pass=True,
        changed_surfaces=["PROCESS_FLOW"],
        gate_surfaces={DESIGN: ["UI_VISUAL"]},
    )
    assert result == {"carry_forward": True, "reason": "UNAFFECTED_GATE"}


def test_changed_gate_surface_requires_rereview():
    result = carry_forward_gate(
        gate=DESIGN,
        previous_pass=True,
        changed_surfaces=["UI_VISUAL"],
        gate_surfaces={DESIGN: ["UI_VISUAL"]},
    )
    assert result == {"carry_forward": False, "reason": "GATE_SURFACE_CHANGED"}


def test_unknown_change_surface_never_carries_forward():
    result = carry_forward_gate(
        gate=DESIGN,
        previous_pass=True,
        changed_surfaces=[],
        gate_surfaces={DESIGN: ["UI_VISUAL"]},
    )
    assert result["carry_forward"] is False


def test_primary_review_over_60_minutes_reroutes():
    result = review_wait_action(
        gate_required=True, wait_age_minutes=60, is_primary=True
    )
    assert result["action"] == "REROUTE_QUALIFIED_REVIEWER"


def test_specialist_review_over_120_minutes_reroutes():
    result = review_wait_action(
        gate_required=True, wait_age_minutes=120, is_primary=False
    )
    assert result["action"] == "REROUTE_QUALIFIED_REVIEWER"


def test_scope_irrelevant_gate_becomes_non_blocking_immediately():
    result = review_wait_action(
        gate_required=False, wait_age_minutes=999, is_primary=False
    )
    assert result == {
        "status": "NON_BLOCKING",
        "action": "REMOVE_FROM_BLOCKING_SET",
    }
