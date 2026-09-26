import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validator", ROOT / "scripts/validate_morning_check_contract.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
BASE = json.loads((ROOT / "data/config/morning-check-v1.json").read_text(encoding="utf-8"))


def test_canonical_contract_is_valid_and_deterministic():
    assert v.validate(BASE) == []
    assert v.validate(BASE) == v.validate(copy.deepcopy(BASE))


def test_version_required():
    c = copy.deepcopy(BASE); c["routine_version"] = ""
    assert v.validate(c)


def test_sections_are_exact_unique_and_ordered():
    for mutate in (lambda s: s[:-1], lambda s: s + [s[0]], lambda s: list(reversed(s))):
        c = copy.deepcopy(BASE); c["sections"] = mutate(c["sections"])
        assert v.validate(c)


def test_unknown_source_class_fails():
    c = copy.deepcopy(BASE); c["sections"][0]["required_inputs"][0]["source_class"] = "unknown"
    assert v.validate(c)


def test_required_input_missing_policy_is_fail_closed():
    c = copy.deepcopy(BASE); c["sections"][0]["required_inputs"][0].pop("missing_policy")
    assert v.validate(c)


def test_silent_zero_or_neutral_policy_fails():
    c = copy.deepcopy(BASE); c["missing_data_policy"] = "ZERO"
    assert v.validate(c)


def test_separation_required():
    c = copy.deepcopy(BASE); c["separation"] = ["fact", "hypothesis"]
    assert v.validate(c)


def test_owner_final_judgment_required():
    c = copy.deepcopy(BASE); c["owner_final_judgment_required"] = False
    assert v.validate(c)


def test_non_object_top_level_fails_closed():
    assert v.validate([]) == ["contract must be a JSON object"]


def test_malformed_section_shape_fails_closed():
    c = copy.deepcopy(BASE); c["sections"][0] = "not-an-object"
    assert "each section must be an object" in v.validate(c)


def test_malformed_input_shape_fails_closed():
    c = copy.deepcopy(BASE); c["sections"][0]["required_inputs"][0] = "not-an-object"
    assert any("input must be an object" in error for error in v.validate(c))


def test_missing_cli_arg_fails_closed(capsys):
    assert v.main(None) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["errors"] == ["contract path argument is required"]


def test_missing_file_fails_closed(tmp_path, capsys):
    assert v.main(tmp_path / "missing.json") == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["errors"][0].startswith("contract file unreadable:")


def test_invalid_json_fails_closed(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text("{not-json", encoding="utf-8")
    assert v.main(path) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"errors": ["contract file contains invalid JSON"], "valid": False}


def test_non_object_json_file_fails_closed(tmp_path, capsys):
    path = tmp_path / "array.json"
    path.write_text("[]", encoding="utf-8")
    assert v.main(path) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"errors": ["contract must be a JSON object"], "valid": False}
