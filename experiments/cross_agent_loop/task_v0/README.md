# Task Family v0: Deterministic Record Normalization

**Version**: 1.0.0  
**Status**: CANONICAL  
**Provider-Neutral**: Yes  
**Phase**: Cross-Agent Loop Phase 1

## Canonical Semantic Packet v1

This section contains the single source of truth for task semantics. All prompt pattern renderings (P1/P2/P3) below preserve this identical semantic information.

### Core Semantics

**Goal**: Implement a pure deterministic Python function that transforms JSON records.

**Input Behavior**: Accept a list of record dictionaries from `input_fixture.json`.

**Output Behavior**: Return a dictionary with two keys:
- `"accepted"`: list of normalized valid records in original input order
- `"rejected"`: list of rejection objects with `{"input": <original>, "reason": <classification>}`

**Normalization Rules**:
- Required fields: `"id"` (string), `"value"` (number), `"category"` (string from allowed set)
- Allowed categories: `"alpha"`, `"beta"`, `"gamma"`
- Normalize `"id"` by stripping whitespace and converting to uppercase
- Normalize `"value"` by rounding to 2 decimal places
- Normalize `"category"` by converting to lowercase
- Preserve order of accepted records matching input order

**Rejection Rules** (fail-closed):
- Missing required field → reject with reason `"missing_required_field"`
- Wrong type (id not string, value not number, category not string) → reject with reason `"invalid_type"`
- Unknown category → reject with reason `"unknown_category"`
- Unknown extra fields are ignored (not a rejection reason)

**Invariants**:
- Pure function: same input always produces same output
- No external I/O, network, database, or file system access
- No randomness or time-dependent behavior
- No mutation of input data structure

**Allowed Mutable Path**: `experiments/cross_agent_loop/task_v0/solution.py`

**Forbidden Actions**:
- Modify any other repository file
- Access production data or investment logic
- Skip CI checks
- Infer or fabricate missing required values

**Required Test/Oracle**: Must pass `oracle_test.py` with all 7 validation checks

**Done Condition**: Oracle returns `PASS`

**No-Skip-CI**: All tests must run and pass in CI

---

## Pattern Renderings

The following three patterns render the canonical semantic packet above into different structural representations. **Information content is identical** across all patterns.

### P1: NATURAL (Natural Language Paragraphs)

**Case IDs**: `P1-R1`, `P1-R2`

**Prompt**:

```
You are tasked with implementing a data normalization function in Python. The function should process a list of record dictionaries and return normalized results while rejecting malformed inputs using a fail-closed approach.

Your implementation should read records from the input_fixture.json file located in the same directory. Each record may contain fields for id, value, and category. The function must validate that all required fields are present and have the correct types. Specifically, id must be a string, value must be a number, and category must be a string. If any required field is missing or has the wrong type, that record should be rejected.

For valid records, apply normalization transformations. The id field should be stripped of any leading or trailing whitespace and converted to uppercase. The value field should be rounded to exactly two decimal places. The category field should be converted to lowercase and must be one of three allowed values: alpha, beta, or gamma. If a record has a category that is not in this allowed set, it should be rejected with the reason being unknown_category.

Records with missing required fields should be rejected with the reason missing_required_field. Records where a required field has the wrong type should be rejected with the reason invalid_type. Note that if a record contains extra fields beyond the required ones, those extra fields should be ignored but should not cause rejection.

The function must return a dictionary with two keys. The accepted key should contain a list of normalized records in the same order they appeared in the input. The rejected key should contain a list of rejection objects, where each object has an input key with the original record and a reason key with the classification of why it was rejected.

Your implementation must be completely deterministic, producing the same output for the same input every time. It should not access any external systems such as networks, databases, or file systems beyond reading the provided input_fixture.json file. The function should not use any randomness or time-dependent behavior, and it must not mutate the original input data structure.

You are only allowed to modify the file experiments/cross_agent_loop/task_v0/solution.py. Do not modify any other files in the repository, access production data or investment logic, or skip any CI checks. When you believe your implementation is complete, it will be validated using oracle_test.py which performs seven validation checks to ensure correctness. The implementation is considered done when the oracle returns PASS.
```

---

### P2: STRUCTURED (Headings and Bullets)

**Case IDs**: `P2-R1`, `P2-R2`

**Prompt**:

```
# Task: Implement Deterministic Record Normalization

## Objective
Implement a Python function for deterministic JSON record transformation with fail-closed validation.

## Input Specification
- **Source**: `input_fixture.json` (same directory)
- **Format**: List of record dictionaries
- **Fields**: `id`, `value`, `category`

## Required Fields and Types
- `id`: string
- `value`: number
- `category`: string (must be from allowed set)

## Allowed Categories
- `alpha`
- `beta`
- `gamma`

## Normalization Rules (for valid records)
1. **id field**:
   - Strip leading/trailing whitespace
   - Convert to uppercase

2. **value field**:
   - Round to 2 decimal places

3. **category field**:
   - Convert to lowercase

4. **Order preservation**:
   - Maintain original input order for accepted records

## Rejection Rules (fail-closed)
- **Missing required field** → reason: `missing_required_field`
- **Wrong type** (id not string, value not number, category not string) → reason: `invalid_type`
- **Unknown category** (not in allowed set) → reason: `unknown_category`
- **Extra fields**: Ignore (do NOT reject)

## Output Format
Return a dictionary with two keys:

```python
{
    "accepted": [
        # List of normalized valid records in original order
    ],
    "rejected": [
        {"input": <original_record>, "reason": <classification>},
        # ...
    ]
}
```

## Constraints
- **Deterministic**: Same input → same output always
- **Pure function**: No side effects
- **No external I/O**: No network, database, or file system access (except reading input_fixture.json)
- **No randomness**: No random numbers or time-dependent behavior
- **No input mutation**: Do not modify original input data structure

## Allowed Modifications
- **File**: `experiments/cross_agent_loop/task_v0/solution.py`
- **Only this file**: No other repository files may be modified

## Forbidden Actions
- Modifying other repository files
- Accessing production data or investment logic
- Skipping CI checks
- Inferring or fabricating missing required values

## Validation
- **Oracle**: `oracle_test.py`
- **Validation checks**: 7 minimum checks
- **Done condition**: Oracle returns `PASS`

## CI Requirements
- All tests must run
- All tests must pass
- No CI skip allowed
```

---

### P3: CONTRACT (Machine-Readable Contract)

**Case IDs**: `P3-R1`, `P3-R2`

**Prompt**:

```yaml
task_contract:
  version: "1.0.0"
  task_family: "deterministic_record_normalization"
  provider_neutral: true
  
  goal: "Implement pure deterministic Python function for JSON record transformation"
  
  input:
    source: "input_fixture.json"
    format: "list[dict]"
    fields:
      id: {type: "string", required: true}
      value: {type: "number", required: true}
      category: {type: "string", required: true, allowed_values: ["alpha", "beta", "gamma"]}
  
  output:
    format: "dict"
    schema:
      accepted: {type: "list[dict]", description: "normalized valid records in input order"}
      rejected: {type: "list[dict]", schema: {input: "dict", reason: "string"}}
  
  normalization_rules:
    id: ["strip_whitespace", "uppercase"]
    value: ["round_to_2_decimals"]
    category: ["lowercase"]
    order: "preserve_input_order_for_accepted"
  
  rejection_reasons:
    missing_required_field: "any required field absent"
    invalid_type: "id not string OR value not number OR category not string"
    unknown_category: "category not in [alpha, beta, gamma]"
  
  rejection_policy: "fail_closed"
  extra_fields_policy: "ignore"
  
  invariants:
    deterministic: true
    pure_function: true
    no_external_io: true
    no_randomness: true
    no_time_dependency: true
    no_input_mutation: true
  
  allowed_mutations:
    paths: ["experiments/cross_agent_loop/task_v0/solution.py"]
  
  forbidden_actions:
    - "modify_other_files"
    - "access_production_data"
    - "access_investment_logic"
    - "skip_ci"
    - "infer_missing_values"
  
  validation:
    oracle: "oracle_test.py"
    minimum_checks: 7
    pass_condition: "oracle_returns_PASS"
  
  ci_policy:
    skip_allowed: false
    all_tests_must_pass: true
```

---

## Provider-Neutral Case Identity

All six benchmark cases are predeclared with provider-neutral IDs:

- **P1-R1**: Pattern 1 (Natural), Repetition 1
- **P1-R2**: Pattern 1 (Natural), Repetition 2
- **P2-R1**: Pattern 2 (Structured), Repetition 1
- **P2-R2**: Pattern 2 (Structured), Repetition 2
- **P3-R1**: Pattern 3 (Contract), Repetition 1
- **P3-R2**: Pattern 3 (Contract), Repetition 2

Provider information is stored in the result schema's `provider` field, not embedded in task/case/oracle artifacts.
