from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Mapping, Sequence

NODE_TYPES = {"OBSERVED", "ASSUMPTION", "DERIVED", "EXTERNAL"}
SCENARIOS = {"COMMON", "BEAR", "BASE", "BULL"}
MODEL_STATUSES = {"COMPLETE", "PARTIAL", "NEEDS_REVIEW", "UNAVAILABLE"}
OPERATIONS = {
    "ADD",
    "SUBTRACT",
    "MULTIPLY",
    "DIVIDE",
    "SUM",
    "PCT_CHANGE",
    "APPLY_MARGIN",
    "PER_SHARE",
}
UNITS = {"JPY", "JPY_MN", "%", "COUNT", "INDEX", "OTHER"}


class DriverModelValidationError(ValueError):
    """Raised when an earnings-driver model violates the canonical contract."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DriverModelValidationError(f"{field} is required")
    return text


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    text = _required_text(value, field).upper()
    if text not in allowed:
        raise DriverModelValidationError(
            f"unsupported {field}: {text}; allowed={sorted(allowed)}"
        )
    return text


def _canonical_number(value: Any, field: str, *, allow_none: bool = False) -> Decimal | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise DriverModelValidationError(f"{field} must be a canonical numeric value")
    if isinstance(value, float) and not math.isfinite(value):
        raise DriverModelValidationError(f"{field} must be finite")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DriverModelValidationError(f"{field} must be numeric") from exc
    if not number.is_finite():
        raise DriverModelValidationError(f"{field} must be finite")
    return number


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def deterministic_driver_model_id(*, security_code: str, target_fiscal_year: str, version: str) -> str:
    payload = {
        "security_code": _required_text(security_code, "security_code"),
        "target_fiscal_year": _required_text(target_fiscal_year, "target_fiscal_year"),
        "version": _required_text(version, "version"),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"earnings-driver:{payload['security_code']}:{payload['target_fiscal_year']}:{digest[:16]}"


@dataclass(frozen=True)
class Formula:
    operation: str
    input_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Formula":
        unknown = set(raw) - {"operation", "input_refs"}
        if unknown:
            raise DriverModelValidationError(f"formula contains unsupported fields: {sorted(unknown)}")
        operation = _enum(raw.get("operation"), "operation", OPERATIONS)
        refs = tuple(_required_text(ref, "input_ref") for ref in (raw.get("input_refs") or []))
        minimum = 1 if operation == "SUM" else 2
        maximum = None if operation in {"SUM", "ADD", "MULTIPLY"} else 2
        if len(refs) < minimum:
            raise DriverModelValidationError(f"{operation} requires at least {minimum} input(s)")
        if maximum is not None and len(refs) != maximum:
            raise DriverModelValidationError(f"{operation} requires exactly {maximum} inputs")
        if len(set(refs)) != len(refs):
            raise DriverModelValidationError("formula input_refs must be unique")
        return cls(operation=operation, input_refs=refs)


@dataclass(frozen=True)
class DriverNode:
    node_id: str
    node_type: str
    metric: str
    scope: str
    scope_id: str | None
    scenario: str
    value: Decimal | None
    unit: str
    target_fiscal_year: str
    formula: Formula | None
    source_refs: tuple[str, ...]
    assumption_text: str | None
    as_of: str
    confidence: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, model_fiscal_year: str) -> "DriverNode":
        allowed = {
            "node_id", "node_type", "metric", "scope", "scope_id", "scenario", "value",
            "unit", "target_fiscal_year", "formula", "source_refs", "assumption_text", "as_of",
            "confidence",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise DriverModelValidationError(f"node contains unsupported fields: {sorted(unknown)}")

        node_type = _enum(raw.get("node_type"), "node_type", NODE_TYPES)
        fiscal_year = _required_text(raw.get("target_fiscal_year"), "target_fiscal_year")
        if fiscal_year != model_fiscal_year:
            raise DriverModelValidationError(
                f"fiscal-year mismatch for {raw.get('node_id')}: {fiscal_year} != {model_fiscal_year}"
            )

        formula_raw = raw.get("formula")
        formula = Formula.from_mapping(formula_raw) if isinstance(formula_raw, Mapping) else None
        value = _canonical_number(raw.get("value"), "value", allow_none=True)

        if node_type == "DERIVED":
            if formula is None:
                raise DriverModelValidationError("DERIVED node requires formula")
        elif formula is not None:
            raise DriverModelValidationError(f"{node_type} node cannot contain formula")

        if node_type == "ASSUMPTION" and not str(raw.get("assumption_text") or "").strip():
            raise DriverModelValidationError("ASSUMPTION node requires assumption_text")

        return cls(
            node_id=_required_text(raw.get("node_id"), "node_id"),
            node_type=node_type,
            metric=_required_text(raw.get("metric"), "metric").upper(),
            scope=_required_text(raw.get("scope"), "scope").upper(),
            scope_id=str(raw.get("scope_id")).strip() if raw.get("scope_id") is not None else None,
            scenario=_enum(raw.get("scenario"), "scenario", SCENARIOS),
            value=value,
            unit=_enum(raw.get("unit"), "unit", UNITS),
            target_fiscal_year=fiscal_year,
            formula=formula,
            source_refs=tuple(_required_text(ref, "source_ref") for ref in (raw.get("source_refs") or [])),
            assumption_text=str(raw.get("assumption_text")).strip() if raw.get("assumption_text") is not None else None,
            as_of=_required_text(raw.get("as_of"), "as_of"),
            confidence=_required_text(raw.get("confidence"), "confidence").upper(),
        )


@dataclass(frozen=True)
class DriverModel:
    driver_model_id: str
    security_code: str
    target_fiscal_year: str
    version: str
    as_of: str
    status: str
    nodes: tuple[DriverNode, ...]
    outputs: Mapping[str, Mapping[str, str | None]]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DriverModel":
        allowed = {
            "driver_model_id", "security_code", "target_fiscal_year", "version", "as_of",
            "status", "nodes", "outputs",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise DriverModelValidationError(f"model contains unsupported fields: {sorted(unknown)}")

        security_code = _required_text(raw.get("security_code"), "security_code")
        target_fiscal_year = _required_text(raw.get("target_fiscal_year"), "target_fiscal_year")
        version = _required_text(raw.get("version"), "version")
        expected_id = deterministic_driver_model_id(
            security_code=security_code,
            target_fiscal_year=target_fiscal_year,
            version=version,
        )
        supplied_id = str(raw.get("driver_model_id") or "").strip()
        if supplied_id and supplied_id != expected_id:
            raise DriverModelValidationError("driver_model_id does not match deterministic identity")

        nodes = tuple(
            DriverNode.from_mapping(node, model_fiscal_year=target_fiscal_year)
            for node in (raw.get("nodes") or [])
        )
        ids = [node.node_id for node in nodes]
        if len(ids) != len(set(ids)):
            raise DriverModelValidationError("node_id must be unique")

        model = cls(
            driver_model_id=expected_id,
            security_code=security_code,
            target_fiscal_year=target_fiscal_year,
            version=version,
            as_of=_required_text(raw.get("as_of"), "as_of"),
            status=_enum(raw.get("status"), "status", MODEL_STATUSES),
            nodes=nodes,
            outputs=deepcopy(raw.get("outputs") or {}),
        )
        model.validate_graph()
        model.validate_outputs()
        return model

    @property
    def node_map(self) -> dict[str, DriverNode]:
        return {node.node_id: node for node in self.nodes}

    def validate_graph(self) -> None:
        nodes = self.node_map
        for node in self.nodes:
            if node.formula is None:
                continue
            for ref in node.formula.input_refs:
                if ref not in nodes:
                    raise DriverModelValidationError(f"unknown input_ref {ref} for {node.node_id}")
                source = nodes[ref]
                if source.scenario not in {"COMMON", node.scenario} and node.scenario != "COMMON":
                    raise DriverModelValidationError(
                        f"scenario mismatch: {node.node_id}({node.scenario}) cannot consume {ref}({source.scenario})"
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise DriverModelValidationError(f"cyclic dependency detected at {node_id}")
            if node_id in visited:
                return
            visiting.add(node_id)
            node = nodes[node_id]
            if node.formula:
                for ref in node.formula.input_refs:
                    visit(ref)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in sorted(nodes):
            visit(node_id)

    def validate_outputs(self) -> None:
        nodes = self.node_map
        for scenario, refs in self.outputs.items():
            scenario_upper = str(scenario).upper()
            if scenario_upper not in {"BEAR", "BASE", "BULL"}:
                raise DriverModelValidationError(f"unsupported output scenario: {scenario}")
            if not isinstance(refs, Mapping):
                raise DriverModelValidationError("output scenario must be a mapping")
            for key in ("net_income_ref", "eps_ref"):
                ref = refs.get(key)
                if ref is None:
                    continue
                if ref not in nodes:
                    raise DriverModelValidationError(f"unknown output ref: {ref}")
                if nodes[ref].scenario not in {"COMMON", scenario_upper}:
                    raise DriverModelValidationError(f"output scenario mismatch for {ref}")


def _infer_unit(operation: str, inputs: Sequence[DriverNode]) -> str:
    units = [node.unit for node in inputs]
    if operation in {"ADD", "SUBTRACT", "SUM"}:
        if len(set(units)) != 1:
            raise DriverModelValidationError(f"{operation} requires compatible units: {units}")
        return units[0]
    if operation == "PCT_CHANGE":
        if len(set(units)) != 1:
            raise DriverModelValidationError("PCT_CHANGE requires same-unit inputs")
        return "%"
    if operation == "APPLY_MARGIN":
        if inputs[1].unit != "%" or inputs[0].unit == "%":
            raise DriverModelValidationError("APPLY_MARGIN requires value × percent")
        return inputs[0].unit
    if operation == "PER_SHARE":
        if inputs[0].unit != "JPY" or inputs[1].unit != "COUNT":
            raise DriverModelValidationError("PER_SHARE v1 requires JPY / COUNT")
        return "JPY"
    if operation == "MULTIPLY":
        non_percent = [unit for unit in units if unit != "%"]
        if len(non_percent) == 1 and len(units) - len(non_percent) >= 1:
            return non_percent[0]
        if sorted(units) == ["COUNT", "JPY"]:
            return "JPY"
        raise DriverModelValidationError(f"MULTIPLY unit combination is unsupported: {units}")
    if operation == "DIVIDE":
        if units[0] == units[1]:
            return "INDEX"
        if units == ["JPY", "COUNT"]:
            return "JPY"
        raise DriverModelValidationError(f"DIVIDE unit combination is unsupported: {units}")
    raise DriverModelValidationError(f"unsupported operation: {operation}")


def _calculate(operation: str, values: Sequence[Decimal]) -> Decimal:
    try:
        if operation in {"ADD", "SUM"}:
            return sum(values, Decimal("0"))
        if operation == "SUBTRACT":
            return values[0] - values[1]
        if operation == "MULTIPLY":
            result = Decimal("1")
            for value in values:
                result *= value
            return result
        if operation == "DIVIDE":
            if values[1] == 0:
                raise DriverModelValidationError("division by zero")
            return values[0] / values[1]
        if operation == "PCT_CHANGE":
            if values[0] == 0:
                raise DriverModelValidationError("PCT_CHANGE baseline cannot be zero")
            return ((values[1] - values[0]) / values[0]) * Decimal("100")
        if operation == "APPLY_MARGIN":
            return values[0] * (values[1] / Decimal("100"))
        if operation == "PER_SHARE":
            if values[1] == 0:
                raise DriverModelValidationError("share count cannot be zero")
            return values[0] / values[1]
    except (DivisionByZero, InvalidOperation) as exc:
        raise DriverModelValidationError(f"invalid arithmetic for {operation}") from exc
    raise DriverModelValidationError(f"unsupported operation: {operation}")


def evaluate_driver_model(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and deterministically evaluate a driver graph.

    Missing explicit input values remain unavailable and propagate as PARTIAL;
    they are never imputed as zero. The function does not mutate ``raw``.
    """

    model = DriverModel.from_mapping(raw)
    nodes = model.node_map
    values: dict[str, Decimal | None] = {node.node_id: node.value for node in model.nodes}
    warnings: list[str] = []
    visiting: set[str] = set()

    def evaluate(node_id: str) -> Decimal | None:
        if values[node_id] is not None:
            return values[node_id]
        node = nodes[node_id]
        if node.formula is None:
            warnings.append(f"MISSING_VALUE:{node_id}")
            return None
        if node_id in visiting:
            raise DriverModelValidationError(f"cyclic dependency detected at {node_id}")
        visiting.add(node_id)
        input_nodes = [nodes[ref] for ref in node.formula.input_refs]
        input_values = [evaluate(ref) for ref in node.formula.input_refs]
        visiting.remove(node_id)
        if any(value is None for value in input_values):
            warnings.append(f"PARTIAL_DERIVATION:{node_id}")
            return None
        inferred = _infer_unit(node.formula.operation, input_nodes)
        if inferred != node.unit:
            raise DriverModelValidationError(
                f"unit mismatch for {node_id}: formula implies {inferred}, node declares {node.unit}"
            )
        calculated = _calculate(node.formula.operation, [value for value in input_values if value is not None])
        if not calculated.is_finite():
            raise DriverModelValidationError(f"non-finite result for {node_id}")
        values[node_id] = calculated
        return calculated

    for node_id in sorted(nodes):
        evaluate(node_id)

    output_values: dict[str, dict[str, float | None]] = {}
    for scenario in sorted(model.outputs):
        refs = model.outputs[scenario]
        output_values[scenario.lower()] = {
            key.replace("_ref", ""): (float(evaluate(ref)) if ref and evaluate(ref) is not None else None)
            for key, ref in refs.items()
        }

    unresolved = sorted(node_id for node_id, value in values.items() if value is None)
    effective_status = model.status
    if unresolved and effective_status == "COMPLETE":
        effective_status = "PARTIAL"
        warnings.append("DECLARED_COMPLETE_BUT_PARTIAL")

    evaluated_nodes = []
    for node in model.nodes:
        evaluated_nodes.append(
            {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "scenario": node.scenario,
                "metric": node.metric,
                "unit": node.unit,
                "value": float(values[node.node_id]) if values[node.node_id] is not None else None,
            }
        )

    return {
        "driver_model_id": model.driver_model_id,
        "security_code": model.security_code,
        "target_fiscal_year": model.target_fiscal_year,
        "as_of": model.as_of,
        "status": effective_status,
        "nodes": evaluated_nodes,
        "outputs": output_values,
        "unresolved_nodes": unresolved,
        "warnings": sorted(set(warnings)),
    }


def dependency_path(raw: Mapping[str, Any], output_node_id: str) -> list[str]:
    """Return deterministic upstream lineage for a scenario output node."""

    model = DriverModel.from_mapping(raw)
    nodes = model.node_map
    if output_node_id not in nodes:
        raise DriverModelValidationError(f"unknown output node: {output_node_id}")
    ordered: list[str] = []
    seen: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        ordered.append(node_id)
        formula = nodes[node_id].formula
        if formula:
            for ref in formula.input_refs:
                walk(ref)

    walk(output_node_id)
    return ordered
