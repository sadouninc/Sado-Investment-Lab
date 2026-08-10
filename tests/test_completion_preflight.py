import pytest

from scripts.completion_preflight import evaluate_payload


def test_owner_gate_without_pass_blocks_completed_close():
    result = evaluate_payload(
        {
            "issue_body": "Owner Acceptance: REQUIRED",
            "owner_comments": [],
        }
    )
    assert result["status"] == "READY_FOR_OWNER_REVIEW"
    assert result["close_allowed"] is False


def test_explicit_owner_pass_allows_close_and_keeps_evidence_ref():
    result = evaluate_payload(
        {
            "issue_body": "Owner Acceptance: REQUIRED",
            "owner_comments": [
                {
                    "ref": "issue-comment:123",
                    "body": "Owner Acceptance: PASS\nReviewed by: 👑サド",
                }
            ],
        }
    )
    assert result["status"] == "OWNER_REVIEWED"
    assert result["close_allowed"] is True
    assert result["evidence_ref"] == "issue-comment:123"


def test_ambiguous_contract_fails_closed():
    result = evaluate_payload(
        {
            "issue_body": "Owner review may be useful.",
            "owner_comments": [],
            "contract_ambiguous": True,
        }
    )
    assert result["status"] == "OWNER_ACCEPTANCE_UNVERIFIED"
    assert result["close_allowed"] is False


def test_issue_without_owner_gate_preserves_normal_close_path():
    result = evaluate_payload(
        {
            "issue_body": "Implementation complete and tests pass.",
            "owner_comments": [],
        }
    )
    assert result["status"] == "NOT_REQUIRED"
    assert result["close_allowed"] is True


def test_invalid_owner_comment_shape_fails_closed_at_input_boundary():
    with pytest.raises(ValueError):
        evaluate_payload(
            {
                "issue_body": "Owner Acceptance: REQUIRED",
                "owner_comments": [{"ref": "issue-comment:123"}],
            }
        )
