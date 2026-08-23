"""
Task Family v0: Deterministic Record Normalization

Reference implementation for the oracle.
This is the canonical solution that solver implementations will be tested against.
"""

import json
from pathlib import Path


def normalize_records(records):
    """
    Normalize a list of record dictionaries.
    
    Args:
        records: List of dictionaries with id, value, and category fields
        
    Returns:
        Dictionary with 'accepted' and 'rejected' keys
    """
    ALLOWED_CATEGORIES = {"alpha", "beta", "gamma"}
    REQUIRED_FIELDS = {"id", "value", "category"}
    
    accepted = []
    rejected = []
    
    for record in records:
        # Check for missing required fields
        missing_fields = REQUIRED_FIELDS - set(record.keys())
        if missing_fields:
            rejected.append({
                "input": record,
                "reason": "missing_required_field"
            })
            continue
        
        # Check types
        if not isinstance(record["id"], str):
            rejected.append({"input": record, "reason": "invalid_type"})
            continue
        if not isinstance(record["value"], (int, float)):
            rejected.append({"input": record, "reason": "invalid_type"})
            continue
        if not isinstance(record["category"], str):
            rejected.append({"input": record, "reason": "invalid_type"})
            continue
        
        # Check category allowed values
        if record["category"].lower() not in ALLOWED_CATEGORIES:
            rejected.append({"input": record, "reason": "unknown_category"})
            continue
        
        # Normalize and accept
        normalized = {
            "id": record["id"].strip().upper(),
            "value": round(record["value"], 2),
            "category": record["category"].lower()
        }
        accepted.append(normalized)
    
    return {"accepted": accepted, "rejected": rejected}
