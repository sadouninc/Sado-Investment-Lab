"""Render P1/P2/P3 prompt patterns from canonical semantic packet."""
import yaml
from pathlib import Path


def load_canonical_packet(packet_path):
    """Load the canonical semantic packet YAML."""
    with open(packet_path, 'r') as f:
        return yaml.safe_load(f)


def render_p1_natural(packet):
    """Render P1: Natural language paragraph format."""
    allowed = ", ".join(packet['required_fields']['category']['allowed_values'])
    
    prompt = f"""You are tasked with implementing a data normalization function in Python. The function should process a list of record dictionaries and return normalized results while rejecting malformed inputs using a fail-closed approach.

Your implementation should accept records as a parameter (list of dictionaries). Each record may contain fields for id, value, and category. The function must validate that all required fields are present and have the correct types. Specifically, id must be a string, value must be a number, and category must be a string. If any required field is missing or has the wrong type, that record should be rejected.

For valid records, apply normalization transformations. The id field should be stripped of any leading or trailing whitespace and converted to uppercase. The value field should be rounded to exactly two decimal places. The category field should be converted to lowercase and must be one of three allowed values: {allowed}. If a record has a category that is not in this allowed set, it should be rejected with the reason being unknown_category.

Records with missing required fields should be rejected with the reason missing_required_field. Records where a required field has the wrong type should be rejected with the reason invalid_type. Note that if a record contains extra fields beyond the required ones, those extra fields should be ignored but should not cause rejection.

The function must return a dictionary with two keys. The accepted key should contain a list of normalized records in the same order they appeared in the input. The rejected key should contain a list of rejection objects, where each object has an input key with the original record and a reason key with the classification of why it was rejected.

Your implementation must be completely deterministic, producing the same output for the same input every time. It should not access any external systems such as networks, databases, or file systems. The function should not use any randomness or time-dependent behavior, and it must not mutate the original input data structure.

You are only allowed to modify the file {packet['allowed_mutations']['paths'][0]}. Do not modify any other files in the repository, access production data or investment logic, or skip any CI checks. When you believe your implementation is complete, it will be validated using {packet['validation']['oracle']} which performs {packet['validation']['minimum_checks']} validation checks to ensure correctness. The implementation is considered done when the oracle returns {packet['validation']['pass_condition'].replace('_', ' ').upper()}."""
    
    return prompt


def render_p2_structured(packet):
    """Render P2: Headings and bullets format."""
    allowed = packet['required_fields']['category']['allowed_values']
    
    prompt = f"""# Task: Implement Deterministic Record Normalization

## Objective
Implement a Python function for deterministic JSON record transformation with fail-closed validation.

## Input Specification
- **Source**: Parameter (list of record dictionaries)
- **Format**: List of record dictionaries
- **Fields**: `id`, `value`, `category`

## Required Fields and Types
- `id`: string
- `value`: number
- `category`: string (must be from allowed set)

## Allowed Categories
{chr(10).join(f'- `{cat}`' for cat in allowed)}

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
{{
    "accepted": [
        # List of normalized valid records in original order
    ],
    "rejected": [
        {{"input": <original_record>, "reason": <classification>}},
        # ...
    ]
}}
```

## Constraints
- **Deterministic**: Same input → same output always
- **Pure function**: No side effects
- **No external I/O**: No network, database, or file system access
- **No randomness**: No random numbers or time-dependent behavior
- **No input mutation**: Do not modify original input data structure

## Allowed Modifications
- **File**: `{packet['allowed_mutations']['paths'][0]}`
- **Only this file**: No other repository files may be modified

## Forbidden Actions
- Modifying other repository files
- Accessing production data or investment logic
- Skipping CI checks
- Inferring or fabricating missing required values

## Validation
- **Oracle**: `{packet['validation']['oracle']}`
- **Validation checks**: {packet['validation']['minimum_checks']} minimum checks
- **Done condition**: Oracle returns `PASS`

## CI Requirements
- All tests must run
- All tests must pass
- No CI skip allowed"""
    
    return prompt


def render_p3_contract(packet):
    """Render P3: Machine-readable YAML contract."""
    # Return the canonical packet directly as YAML string
    return yaml.dump(packet, default_flow_style=False, sort_keys=False)


def render_all_patterns():
    """Render all three patterns from canonical packet."""
    base = Path(__file__).parent
    packet_path = base / "canonical_semantic_packet.yaml"
    
    packet = load_canonical_packet(packet_path)
    
    patterns = {
        'P1_NATURAL': render_p1_natural(packet),
        'P2_STRUCTURED': render_p2_structured(packet),
        'P3_CONTRACT': render_p3_contract(packet)
    }
    
    # Write patterns to rendered directory
    rendered_dir = base / "rendered"
    rendered_dir.mkdir(exist_ok=True)
    
    for pattern_name, content in patterns.items():
        output_file = rendered_dir / f"{pattern_name.lower()}.txt"
        with open(output_file, 'w') as f:
            f.write(content)
    
    return patterns


if __name__ == "__main__":
    patterns = render_all_patterns()
    print("✓ Rendered all patterns from canonical semantic packet")
    for name in patterns:
        print(f"  - {name}")

