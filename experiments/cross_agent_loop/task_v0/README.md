# Cross-Agent Loop Phase 1: Task Family v0

**Version**: v0  
**Status**: READY_FOR_IMPLEMENTATION  
**Provider-Neutral**: Yes  
**Deterministic**: Yes  
**Authority**: STANDARD

## Overview

This task family implements a pure deterministic Python transformation for normalizing JSON records. The task is provider-neutral and requires no access to production code, investment data, network, or secrets.

## Canonical Semantic Packet v1

All three prompt patterns (P1, P2, P3) below contain **identical semantic information**. They differ only in representation/structure. Each pattern communicates the same:
- Goal
- Input/output behavior
- Allowed mutable path
- Forbidden actions/paths
- Invariants
- Required test/oracle command
- Done condition
- No-skip-ci

---

## Pattern P1: NATURAL

Your task is to implement a deterministic record normalizer in Python. You will receive a list of JSON records that may contain valid or invalid fields, and you must process them according to strict rules.

Each input record can have fields like "id", "name", "value", and "status". Your normalizer should accept records that have all required fields ("id" and "name") and normalize them by converting the "name" field to lowercase and ensuring "value" defaults to 0 if not present. The "status" field should be set to "active" when not provided. Records missing required fields like "id" or "name" should be rejected with an explicit error classification. Any record containing unknown fields beyond the expected set should also be rejected to maintain a fail-closed security posture.

The output must preserve the input ordering of accepted records. Never infer or guess missing required values—always reject such records explicitly. Your implementation should be deterministic, producing identical output when run multiple times with the same input.

You are allowed to modify only the file `experiments/cross_agent_loop/task_v0/solution.py`. This file must export a public function named `normalize_records` that accepts a list of dictionaries and returns a dictionary with two keys: "normalized" (list of accepted records) and "rejected" (list of error objects with "record" and "reason" fields).

Do not modify any other files in the repository. Do not access network resources, read from databases, or interact with any production systems. Do not skip CI checks—all tests must pass.

The oracle will verify your implementation by checking that: syntax and imports succeed, the required function signature exists, valid fixtures are normalized exactly as expected, malformed required fields are rejected, unknown fields do not result in successful normalization, repeated runs produce identical output, and only the allowed solver path was modified.

You are done when the oracle test suite at `experiments/cross_agent_loop/task_v0/oracle_test.py` passes completely. Run it with: `python -m pytest experiments/cross_agent_loop/task_v0/oracle_test.py -v`

---

## Pattern P2: STRUCTURED

### Goal
Implement a deterministic record normalizer in `experiments/cross_agent_loop/task_v0/solution.py`.

### Input/Output Behavior

**Input**: List of JSON record dictionaries

**Expected Fields**:
- `id` (required): Record identifier
- `name` (required): Record name
- `value` (optional): Numeric value
- `status` (optional): Status string

**Normalization Rules**:
- Convert `name` to lowercase
- Default `value` to `0` if missing
- Default `status` to `"active"` if missing
- Preserve input record ordering
- Reject records missing required fields (`id` or `name`)
- Reject records with unknown fields (fail-closed)
- Never infer or guess missing required values

**Output**: Dictionary with two keys:
- `normalized`: List of accepted, normalized records
- `rejected`: List of error objects, each with:
  - `record`: The rejected input record
  - `reason`: Explicit error classification string

### Required Function Signature
```python
def normalize_records(records: list) -> dict:
    """
    Normalize a list of records according to the task specification.
    
    Args:
        records: List of record dictionaries
        
    Returns:
        Dictionary with 'normalized' and 'rejected' keys
    """
    pass
```

### Allowed Mutable Path
- `experiments/cross_agent_loop/task_v0/solution.py` (only this file)

### Forbidden Actions/Paths
- Do not modify any other files
- Do not access network resources
- Do not read from databases
- Do not interact with production systems
- Do not access investment data
- Do not skip CI checks

### Invariants
- Implementation must be deterministic (same input → same output)
- Output must preserve input ordering of accepted records
- Rejection must be explicit with clear error classification

### Required Test/Oracle Command
```bash
python -m pytest experiments/cross_agent_loop/task_v0/oracle_test.py -v
```

### Oracle Verification Checks
1. Syntax/import succeeds
2. Required public function signature exists
3. Valid fixture normalized exactly as expected
4. Malformed required field rejected
5. Unknown field/state does not become normal success
6. Deterministic repeated run (identical output)
7. Only allowed solver path changed

### Done Condition
Oracle test suite passes completely with result: `PASS`

---

## Pattern P3: CONTRACT

```yaml
work_contract:
  version: 1
  goal: "Implement deterministic record normalizer in solution.py"
  task_family: "task_v0"
  status: READY_FOR_IMPLEMENTATION
  authority: STANDARD
  
  input_schema:
    type: "list[dict]"
    record_schema:
      id:
        required: true
        type: "string|number"
      name:
        required: true
        type: "string"
      value:
        required: false
        type: "number"
        default: 0
      status:
        required: false
        type: "string"
        default: "active"
    unknown_fields: "REJECT"
  
  output_schema:
    type: "dict"
    normalized:
      type: "list[dict]"
      description: "Accepted records with normalization applied"
    rejected:
      type: "list[dict]"
      description: "Rejected records with error classification"
      item_schema:
        record: "original input record"
        reason: "explicit error string"
  
  normalization_rules:
    - "convert name to lowercase"
    - "default value to 0 if missing"
    - "default status to 'active' if missing"
    - "preserve input ordering"
    - "reject missing required fields (id, name)"
    - "reject records with unknown fields"
    - "never infer missing required values"
  
  behavioral_invariants:
    deterministic: true
    ordering_preserved: true
    fail_closed: true
  
  allowed_paths:
    - "experiments/cross_agent_loop/task_v0/solution.py"
  
  forbidden_actions:
    - "modify other files"
    - "access network"
    - "access database"
    - "access production systems"
    - "access investment data"
    - "skip CI checks"
  
  required_function:
    name: "normalize_records"
    signature: "def normalize_records(records: list) -> dict"
    visibility: "public"
  
  oracle_checks:
    - "syntax_import_succeeds"
    - "function_signature_exists"
    - "valid_fixture_normalized_exactly"
    - "malformed_required_field_rejected"
    - "unknown_field_rejected"
    - "deterministic_repeated_run"
    - "only_allowed_path_changed"
  
  acceptance_test:
    command: "python -m pytest experiments/cross_agent_loop/task_v0/oracle_test.py -v"
    done_condition: "PASS"
    no_skip_ci: true
```

---

**End of Canonical Semantic Packet v1**
