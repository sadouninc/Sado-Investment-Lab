from scripts.ai_production_acceptance_fixture import normalize_acceptance_token


def test_preserves_internal_characters_and_trims_outer_whitespace() -> None:
    assert normalize_acceptance_token("  hello world  ") == "hello world"
    assert normalize_acceptance_token("token") == "token"
    assert normalize_acceptance_token("\tmixed \n whitespace\n") == "mixed \n whitespace"
    assert normalize_acceptance_token(" a b  c ") == "a b  c"


def test_empty_or_whitespace_only_returns_none() -> None:
    assert normalize_acceptance_token("") is None
    assert normalize_acceptance_token("   ") is None
    assert normalize_acceptance_token("\t\n\r ") is None


def test_none_numbers_and_containers_return_none() -> None:
    assert normalize_acceptance_token(None) is None
    assert normalize_acceptance_token(0) is None
    assert normalize_acceptance_token(1) is None
    assert normalize_acceptance_token(1.5) is None
    assert normalize_acceptance_token([]) is None
    assert normalize_acceptance_token(["a"]) is None
    assert normalize_acceptance_token({}) is None
    assert normalize_acceptance_token({"a": "b"}) is None
    assert normalize_acceptance_token(()) is None
    assert normalize_acceptance_token(True) is None
    assert normalize_acceptance_token(False) is None
