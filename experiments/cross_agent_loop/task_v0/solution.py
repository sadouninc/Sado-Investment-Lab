"""Solver mutation target for Cross-Agent Loop Phase 1.

This is a reference implementation for oracle self-testing.
In a real benchmark run, this file would be overwritten by the AI solver.
"""


def normalize_records(records: list) -> dict:
    """Normalize a list of records according to task specification.
    
    Args:
        records: List of record dictionaries
        
    Returns:
        Dictionary with 'normalized' and 'rejected' keys
    """
    normalized = []
    rejected = []
    
    # Expected fields
    required_fields = {"id", "name"}
    optional_fields = {"value", "status"}
    allowed_fields = required_fields | optional_fields
    
    for record in records:
        # Check for required fields
        if not all(field in record for field in required_fields):
            missing = required_fields - set(record.keys())
            rejected.append({
                "record": record,
                "reason": f"Missing required field(s): {', '.join(missing)}"
            })
            continue
        
        # Check for unknown fields (fail-closed)
        record_fields = set(record.keys())
        if not record_fields.issubset(allowed_fields):
            unknown = record_fields - allowed_fields
            rejected.append({
                "record": record,
                "reason": f"Unknown field(s): {', '.join(unknown)}"
            })
            continue
        
        # Normalize accepted record
        normalized_record = {
            "id": record["id"],
            "name": record["name"].lower(),
            "value": record.get("value", 0),
            "status": record.get("status", "active")
        }
        normalized.append(normalized_record)
    
    return {"normalized": normalized, "rejected": rejected}
