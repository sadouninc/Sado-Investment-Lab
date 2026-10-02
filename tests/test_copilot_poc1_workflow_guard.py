from scripts.copilot_poc1_workflow_guard import generic_forbidden_paths, is_exact_workflow_exception

def test_changed_workflow_path_blocked_by_default():
    assert generic_forbidden_paths([".github/workflows/queue-auto-promotion-consumer.yml"], []) == [".github/workflows/queue-auto-promotion-consumer.yml"]

def test_exact_contracted_workflow_path_is_allowed_through_generic_guard():
    allowed = [".github/workflows/copilot-poc1.yml", "tests/*", "scripts/*"]
    assert generic_forbidden_paths([".github/workflows/copilot-poc1.yml"], allowed) == []
    assert is_exact_workflow_exception(".github/workflows/copilot-poc1.yml", allowed)

def test_wildcard_workflow_contract_does_not_bypass_generic_guard():
    allowed = [".github/workflows/*"]
    path = ".github/workflows/queue-auto-promotion-consumer.yml"
    assert generic_forbidden_paths([path], allowed) == [path]
    assert not is_exact_workflow_exception(path, allowed)

def test_second_uncontracted_workflow_file_remains_blocked():
    allowed = [".github/workflows/copilot-poc1.yml"]
    assert generic_forbidden_paths([".github/workflows/copilot-poc1.yml", ".github/workflows/other-workflow.yml"], allowed) == [".github/workflows/other-workflow.yml"]

def test_dependency_lockfile_generic_forbidden_behavior_unchanged():
    changed = ["package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "poetry.lock", "uv.lock", "scripts/foo.py"]
    assert generic_forbidden_paths(changed, ["scripts/*"]) == changed[:-1]

def test_exact_workflow_file_in_subdirectory_is_not_matched():
    path = ".github/workflows/nested/copilot-poc1.yml"
    assert not is_exact_workflow_exception(path, [path])

def test_yaml_extension_also_supported_for_exact_match():
    path = ".github/workflows/copilot-poc1.yaml"
    assert generic_forbidden_paths([path], [path]) == []
