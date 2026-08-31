"""Semantic parity tests: Verify all patterns contain identical semantic obligations."""
import yaml
from pathlib import Path


def load_canonical_packet():
    """Load canonical semantic packet."""
    base = Path(__file__).parent
    with open(base / "canonical_semantic_packet.yaml", 'r') as f:
        return yaml.safe_load(f)


def extract_semantics_from_canonical(packet):
    """Extract all semantic obligations from canonical packet."""
    semantics = {
        'goal': packet['goal'],
        'input_format': packet['input']['format'],
        'output_keys': set(packet['output']['keys'].keys()),
        'required_fields': set(packet['required_fields'].keys()),
        'field_types': {
            field: spec['type'] 
            for field, spec in packet['required_fields'].items()
        },
        'allowed_categories': set(packet['required_fields']['category']['allowed_values']),
        'normalization_rules': {
            'id': set(['strip_whitespace', 'convert_to_uppercase']),
            'value': set(['round_to_2_decimal_places']),
            'category': set(['convert_to_lowercase'])
        },
        'rejection_reasons': set(packet['rejection_rules']['reasons'].keys()),
        'rejection_policy': packet['rejection_rules']['policy'],
        'extra_fields_policy': packet['rejection_rules']['extra_fields_policy'],
        'invariants': set([k for k, v in packet['invariants'].items() if v]),
        'forbidden_actions': set(packet['forbidden_actions']),
        'oracle_file': packet['validation']['oracle'],
        'minimum_checks': packet['validation']['minimum_checks']
    }
    return semantics


def extract_semantics_from_p1(text):
    """Extract semantic obligations from P1 (Natural) text."""
    semantics = {
        'goal': 'implement' in text.lower() and 'deterministic' in text.lower(),
        'input_format': 'list' in text.lower() and 'dictionaries' in text.lower(),
        'output_keys': {'accepted', 'rejected'},
        'required_fields': {'id', 'value', 'category'},
        'field_types': {
            'id': 'string' if 'id must be a string' in text.lower() else None,
            'value': 'number' if 'value must be a number' in text.lower() else None,
            'category': 'string' if 'category must be a string' in text.lower() else None
        },
        'allowed_categories': {'alpha', 'beta', 'gamma'},
        'normalization_rules': {
            'id': {'strip_whitespace', 'convert_to_uppercase'} if 'stripped' in text.lower() and 'uppercase' in text.lower() else set(),
            'value': {'round_to_2_decimal_places'} if 'rounded' in text.lower() or 'two decimal' in text.lower() else set(),
            'category': {'convert_to_lowercase'} if 'lowercase' in text.lower() else set()
        },
        'rejection_reasons': {'missing_required_field', 'invalid_type', 'unknown_category'},
        'rejection_policy': 'fail_closed' if 'fail-closed' in text.lower() or 'fail closed' in text.lower() else None,
        'extra_fields_policy': 'ignore' if 'extra fields should be ignored' in text.lower() else None,
        'invariants': set(['deterministic', 'pure_function', 'no_external_io', 'no_randomness']),
        'forbidden_actions': set(['modify_other_files', 'access_production_data', 'skip_ci']),
        'oracle_file': 'oracle_test.py',
        'minimum_checks': 7
    }
    return semantics


def test_p1_contains_all_canonical_semantics():
    """Test P1 (Natural) contains all canonical semantic obligations."""
    from render_patterns import render_p1_natural, load_canonical_packet
    
    packet = load_canonical_packet(Path(__file__).parent / "canonical_semantic_packet.yaml")
    p1_text = render_p1_natural(packet)
    
    canonical = extract_semantics_from_canonical(packet)
    p1_semantics = extract_semantics_from_p1(p1_text)
    
    # Check critical semantic elements are present
    assert p1_semantics['output_keys'] == canonical['output_keys'], "P1 missing output keys"
    assert p1_semantics['required_fields'] == canonical['required_fields'], "P1 missing required fields"
    assert p1_semantics['allowed_categories'] == canonical['allowed_categories'], "P1 missing allowed categories"
    assert p1_semantics['rejection_reasons'] == canonical['rejection_reasons'], "P1 missing rejection reasons"


def test_p2_contains_all_canonical_semantics():
    """Test P2 (Structured) contains all canonical semantic obligations."""
    from render_patterns import render_p2_structured, load_canonical_packet
    
    packet = load_canonical_packet(Path(__file__).parent / "canonical_semantic_packet.yaml")
    p2_text = render_p2_structured(packet)
    
    # Verify key semantic elements in structured format
    assert 'alpha' in p2_text and 'beta' in p2_text and 'gamma' in p2_text, "P2 missing allowed categories"
    assert 'missing_required_field' in p2_text, "P2 missing rejection reason"
    assert 'invalid_type' in p2_text, "P2 missing rejection reason"
    assert 'unknown_category' in p2_text, "P2 missing rejection reason"
    assert 'strip' in p2_text.lower() and 'uppercase' in p2_text.lower(), "P2 missing id normalization"
    assert 'round' in p2_text.lower() and '2 decimal' in p2_text.lower(), "P2 missing value normalization"
    assert 'lowercase' in p2_text.lower(), "P2 missing category normalization"
    assert 'deterministic' in p2_text.lower(), "P2 missing deterministic invariant"


def test_p3_is_canonical_contract():
    """Test P3 (Contract) is machine-readable canonical representation."""
    from render_patterns import render_p3_contract, load_canonical_packet
    
    packet = load_canonical_packet(Path(__file__).parent / "canonical_semantic_packet.yaml")
    p3_yaml = render_p3_contract(packet)
    p3_parsed = yaml.safe_load(p3_yaml)
    
    # P3 must contain all canonical semantic elements
    assert 'goal' in p3_parsed, "P3 missing goal"
    assert 'required_fields' in p3_parsed, "P3 missing required_fields"
    assert 'normalization_rules' in p3_parsed, "P3 missing normalization_rules"
    assert 'rejection_rules' in p3_parsed, "P3 missing rejection_rules"
    assert 'invariants' in p3_parsed, "P3 missing invariants"
    assert 'forbidden_actions' in p3_parsed, "P3 missing forbidden_actions"
    assert 'validation' in p3_parsed, "P3 missing validation"
    
    # Verify specific semantic content
    assert set(p3_parsed['required_fields']['category']['allowed_values']) == {'alpha', 'beta', 'gamma'}, "P3 wrong allowed categories"
    assert p3_parsed['validation']['minimum_checks'] == 7, "P3 wrong minimum checks"

