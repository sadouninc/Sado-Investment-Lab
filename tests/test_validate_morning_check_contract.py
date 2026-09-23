import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "config" / "morning-check-v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_morning_check_contract.py"

spec = importlib.util.spec_from_file_location("morning_contract_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def valid_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_repository_contract_is_valid_and_deterministic():
    contract = valid_contract()
    assert validator.validate_contract(contract) == []
    assert validator.validate_contract(contract) == validator.validate_contract(copy.deepcopy(contract))


def test_routine_version_is_required_and_non_empty():
    contract = valid_contract()
    contract.pop("routine_version")
    assert "routine_version" in " ".join(validator.validate_contract(contract))
    contract["routine_version"] = ""
    assert "routine_version" in " ".join(validator.validate_contract(contract))


def test_required_sections_are_exact_unique_and_ordered():
    contract = valid_contract()
    contract["sections"][0], contract["sections"][1] = contract["sections"][1], contract["sections"][0]
    assert "required 8 names exactly once and in order" in " ".join(validator.validate_contract(contract))
    contract = valid_contract()
    contract["sections"].pop()
    assert "required 8 names exactly once and in order" in " ".join(validator.validate_contract(contract))
    contract = valid_contract()
    contract["sections"][1]["name"] = contract["sections"][0]["name"]
    assert "required 8 names exactly once and in order" in " ".join(validator.validate_contract(contract))


def test_unknown_source_class_fails():
    contract = valid_contract()
    contract["sections"][0]["required_inputs"][0]["source_class"] = "untrusted_magic"
    assert "source_class is not allowed" in " ".join(validator.validate_contract(contract))


def test_required_input_missing_policy_is_required_and_fail_closed():
    contract = valid_contract()
    contract["sections"][0]["required_inputs"][0].pop("missing_policy")
    assert "missing_policy must be UNKNOWN or MISSING" in " ".join(validator.validate_contract(contract))
    for unsafe in ("0", "zero", "neutral", 0, None):
        contract = valid_contract()
        contract["sections"][0]["required_inputs"][0]["missing_policy"] = unsafe
        assert "missing_policy must be UNKNOWN or MISSING" in " ".join(validator.validate_contract(contract))


def test_fact_hypothesis_action_candidate_separation_is_required():
    for key in ("fact", "hypothesis", "action_candidate"):
        contract = valid_contract()
        contract["separation"][key] = False
        assert "separation must be explicitly true" in " ".join(validator.validate_contract(contract))


def test_owner_final_judgment_is_required():
    contract = valid_contract()
    contract["owner_final_judgment_required"] = False
    assert "owner_final_judgment_required must be true" in " ".join(validator.validate_contract(contract))


def test_validator_is_pure_read_only_by_construction():
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    forbidden = ("requests", "urllib", "httpx", "github", "broker", "openai", "subprocess")
    assert not any(token in source.lower() for token in forbidden)
