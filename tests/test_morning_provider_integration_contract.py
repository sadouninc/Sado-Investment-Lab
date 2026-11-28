"""Combined Morning Dataset regression gate for all eight providers (#982).

Each provider has its own unit tests, but those do not prove the combined
contract: every provider result flows through ``collect_providers`` ->
``dataset_inputs`` -> ``build_dataset`` -> ``validate_dataset`` and the final
dataset must still be strict JSON (``allow_nan=False``) with source status,
warnings and quality counts that match what each provider actually reported.

All inputs are synthetic fixtures written to a temporary directory. No live,
private or network data is used: the market provider receives an in-memory
fetcher. The provider wiring mirrors the ``--repo-*`` / ``--live-market`` /
``--selector-candidates`` / ``--investor-dna`` path of
``scripts/generate_morning_dataset.py``.

When a provider lets a non-serializable value through, the failure message
names the exact JSON path so it can be returned to that provider's owner.
"""

from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Callable
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import build_dataset_from_providers
from scripts.morning_dataset.providers import (
    EVENT_KEYS,
    EXPECTED_SOURCES,
    MARKET_SYMBOLS,
    CandidateSelectorProvider,
    CandidatesProvider,
    CapitalProvider,
    EventsProvider,
    JsonFileProvider,
    MarketProvider,
    PortfolioProvider,
    SectorRotationProvider,
    WatchlistProvider,
)
from scripts.morning_dataset.providers.sector_rotation import _previous_market_business_day
from scripts.morning_dataset.schema import EMPTY_DATASET

TODAY = date(2026, 11, 27)
SECTOR_AS_OF = _previous_market_business_day(TODAY)
GENERATED_AT = datetime(2026, 11, 27, 6, 0, tzinfo=timezone.utc)
SECTOR_COUNT = 17
STATUSES = ("OK", "PARTIAL", "STALE", "MISSING")


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------


def _chart(closes: list[Any]) -> dict[str, Any]:
    base = int(datetime(2026, 11, 25, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [base + 86400 * index for index in range(len(closes))],
                    "indicators": {"quote": [{"close": closes}]},
                }
            ],
            "error": None,
        }
    }


def market_fetcher(overrides: dict[str, list[Any]] | None = None) -> Callable[[str], dict[str, Any]]:
    overrides = overrides or {}

    def fetch(symbol: str) -> dict[str, Any]:
        return _chart(overrides.get(symbol, [100.0, 101.5]))

    return fetch


def write_portfolio(path: Path, *, as_of: str, avg_price: str = "0.0") -> None:
    # Written as raw text so non-standard literals (NaN, 1e400) can be injected.
    path.write_text(
        "{"
        '"verification_status": "VERIFIED", '
        f'"as_of": "{as_of}", '
        '"positions": [{"security_code": "9001", "name": "Synthetic Rail", '
        f'"quantity": 100, "avg_price": {avg_price}}}]'
        "}",
        encoding="utf-8",
    )


CAPITAL_COLUMNS = (
    "cash_buying_power",
    "margin_buying_power",
    "cash_ratio",
    "margin_exposure",
    "margin_ratio",
    "total_exposure",
    "reserve_amount",
)


def write_capital(path: Path, *, snapshot_at: str, facts: dict[str, Any] | None = None, source: Any = "synthetic") -> None:
    values = {
        "cash_buying_power": 0.0,  # true zero must survive as a fact
        "margin_buying_power": 250000.0,
        "cash_ratio": 0.0,
        "margin_exposure": 0.0,
        "margin_ratio": 0.0,
        "total_exposure": 120000.0,
        "reserve_amount": 50000.0,
    }
    values.update(facts or {})
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE capital_snapshots (id INTEGER PRIMARY KEY, snapshot_at TEXT, "
            + ", ".join(f"{column} REAL" for column in CAPITAL_COLUMNS)
            + ", source TEXT, source_version TEXT)"
        )
        conn.execute(
            "INSERT INTO capital_snapshots (snapshot_at, "
            + ", ".join(CAPITAL_COLUMNS)
            + ", source, source_version) VALUES (?, "
            + ", ".join("?" for _ in CAPITAL_COLUMNS)
            + ", ?, ?)",
            (snapshot_at, *(values[column] for column in CAPITAL_COLUMNS), source, "v1"),
        )


def write_candidates_db(path: Path, *, generated_at: str, today_score: Any = 0.0, invalid_utf8_status: bool = False) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE candidates (
                id INTEGER PRIMARY KEY, generated_at TEXT, security_code TEXT, horizon TEXT,
                universe_state TEXT, long_score REAL, today_score REAL, risk_score REAL,
                personal_fit REAL, capital_feasibility REAL, rotation_score REAL,
                rank INTEGER, status TEXT, confidence REAL, model_name TEXT, model_version TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE candidate_factors (
                id INTEGER PRIMARY KEY, candidate_id INTEGER, factor_type TEXT, factor_key TEXT,
                value_numeric REAL, value_text TEXT, contribution REAL, polarity TEXT,
                source_reference TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO candidates (generated_at, security_code, horizon, universe_state, long_score, "
            "today_score, risk_score, personal_fit, capital_feasibility, rotation_score, rank, status, "
            "confidence, model_name, model_version) VALUES (?, '9001', 'SWING', 'ACTIVE', 0.5, ?, 0.2, "
            "0.0, 1.0, 0.0, 1, 'WATCH', 0.7, 'synthetic', 'v1')",
            (generated_at, today_score),
        )
        conn.execute(
            "INSERT INTO candidate_factors (candidate_id, factor_type, factor_key, value_numeric, "
            "value_text, contribution, polarity, source_reference) VALUES (1, 'TECH', 'trend', 0.0, "
            "'flat', 0.0, 'NEUTRAL', 'synthetic')"
        )
        if invalid_utf8_status:
            conn.execute("UPDATE candidates SET status = CAST(x'ff' AS TEXT) WHERE id = 1")


def write_selector(path: Path, *, as_of: str, total_priority: str = "0.0") -> None:
    path.write_text(
        "{"
        f'"as_of": "{as_of}", '
        '"ranked_candidates": [{"security_code": "9001", "company_name": "Synthetic Rail", '
        f'"total_priority": {total_priority}, "candidate_sources": ["synthetic"], '
        '"research_status": "WATCH", "selection_reason": "synthetic fixture", '
        '"unused_metric": NaN}]'
        "}",
        encoding="utf-8",
    )


def write_investor_dna(path: Path, *, as_of: str, fit: str = "0.0") -> None:
    path.write_text(
        "{"
        f'"as_of": "{as_of}", '
        '"native_dna": {"style": "synthetic"}, '
        f'"environment_fit": {{"score": {fit}}}, '
        '"style_drift": null, "risk_patterns": []'
        "}",
        encoding="utf-8",
    )


def write_events(path: Path, *, as_of: str, extra_field: str = "0") -> None:
    coverage = ", ".join(f'"{key}": true' for key in EVENT_KEYS)
    categories = ", ".join(
        f'"{key}": []' if key != "earnings" else
        f'"earnings": [{{"title": "Synthetic earnings", "date": "{TODAY.isoformat()}", "consensus": {extra_field}}}]'
        for key in EVENT_KEYS
    )
    path.write_text(
        "{"
        f'"as_of": "{as_of}", '
        f'"coverage": {{{coverage}}}, '
        f'"events": {{{categories}}}'
        "}",
        encoding="utf-8",
    )


def write_watchlist(path: Path, *, as_of: str | None, raw: bytes | None = None) -> None:
    if raw is not None:
        path.write_bytes(raw)
        return
    lines = ["# Current Status", "", "## Current Focus"]
    if as_of is not None:
        lines.append(f"> as_of: {as_of}")
    lines += ["- 9001 Synthetic Rail の出来高確認", "", "## Other", "- not a watch item"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sector_history(path: Path, *, as_of: str, flow_score_literal: str = "0") -> None:
    rows = []
    for index in range(SECTOR_COUNT):
        score = flow_score_literal if index == 0 else str(index)
        rows.append(
            "{"
            f'"kind": "SECTOR", "id": "S{index:02d}", "name": "Sector {index:02d}", '
            f'"as_of": "{as_of}", "state": "NEUTRAL", "previous_state": null, "state_since": null, '
            f'"flow_score": {score}, '
            '"scores": {"relative_strength": 0, "activity": 0.5, "breadth": null, "heat": 1, "acceleration": 0}, '
            '"data_completeness": "OK", "evidence": []'
            "}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


class Fixture:
    """Paths of one synthetic repository layout."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.portfolio = root / "portfolio.json"
        self.capital = root / "capital.db"
        self.candidates_db = root / "candidates.db"
        self.selector = root / "candidate-selector.json"
        self.investor_dna = root / "investor-dna.json"
        self.events = root / "calendar.json"
        self.watchlist = root / "Current_Status.md"
        self.sectors = root / "sector-history.jsonl"

    def write_all_fresh(self) -> None:
        today = TODAY.isoformat()
        write_portfolio(self.portfolio, as_of=today)
        write_capital(self.capital, snapshot_at=f"{today}T05:00:00+09:00")
        write_candidates_db(self.candidates_db, generated_at=f"{today}T05:00:00+09:00")
        write_selector(self.selector, as_of=today)
        write_investor_dna(self.investor_dna, as_of=today)
        write_events(self.events, as_of=today)
        write_watchlist(self.watchlist, as_of=today)
        write_sector_history(self.sectors, as_of=SECTOR_AS_OF.isoformat())

    def providers(self, *, candidates: str = "sqlite", fetcher: Callable[[str], dict[str, Any]] | None = None) -> list[Any]:
        if candidates == "sqlite":
            candidate_provider: Any = CandidatesProvider(self.candidates_db, today=TODAY)
        elif candidates == "selector":
            candidate_provider = CandidateSelectorProvider(self.selector, today=TODAY)
        else:  # pragma: no cover - test misuse
            raise ValueError(candidates)
        return [
            MarketProvider(fetcher or market_fetcher()),
            PortfolioProvider(self.portfolio, today=TODAY),
            CapitalProvider(self.capital, today=TODAY),
            candidate_provider,
            EventsProvider(self.events, today=TODAY),
            WatchlistProvider(self.watchlist, today=TODAY),
            SectorRotationProvider(self.sectors, report_date=TODAY),
            JsonFileProvider("investor_dna", self.investor_dna),
        ]


# ---------------------------------------------------------------------------
# Contract assertions
# ---------------------------------------------------------------------------


def nonfinite_paths(value: Any, path: str = "$") -> list[str]:
    """JSON paths of values that strict JSON cannot represent."""
    found: list[str] = []
    if isinstance(value, float):
        if not math.isfinite(value):
            found.append(path)
    elif isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                found.append(f"{path}<non-string key {type(key).__name__}>")
            found.extend(nonfinite_paths(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(nonfinite_paths(child, f"{path}[{index}]"))
    elif value is not None and not isinstance(value, (str, int, bool)):
        found.append(f"{path}<{type(value).__name__}>")
    return found


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-standard JSON constant in output: {name}")


class IntegrationContractTest(unittest.TestCase):
    def build(self, fixture: Fixture, **kwargs: Any) -> dict[str, Any]:
        return build_dataset_from_providers(
            fixture.providers(**kwargs),
            generated_at=GENERATED_AT,
            as_of=TODAY,
        )

    def assert_contract(self, dataset: dict[str, Any], expected: dict[str, str]) -> None:
        self.assertEqual(set(EXPECTED_SOURCES), set(expected), "test must declare all eight sources")

        offending = nonfinite_paths(dataset)
        self.assertEqual([], offending, f"non-serializable values reached the dataset: {offending}")
        text = json.dumps(dataset, ensure_ascii=False, allow_nan=False)
        self.assertEqual(dataset, json.loads(text, parse_constant=_reject_constant))

        rows = dataset["source_status"]
        self.assertEqual(list(EXPECTED_SOURCES), [row["name"] for row in rows])
        actual = {row["name"]: row["status"] for row in rows}
        self.assertEqual(expected, actual)
        for row in rows:
            if row["status"] != "OK":
                self.assertTrue(row["reason"], f"{row['name']} is {row['status']} without a reason")

        counts = {status: sum(1 for value in expected.values() if value == status) for status in STATUSES}
        total = len(EXPECTED_SOURCES)
        usable = counts["OK"] + counts["PARTIAL"] + counts["STALE"]
        quality = dataset["data_quality"]
        self.assertEqual(counts, quality["source_counts"])
        self.assertEqual(counts["OK"], quality["ok_sources"])
        self.assertEqual(counts["OK"], quality["available_sources"])
        self.assertEqual(usable, quality["usable_sources"])
        self.assertEqual(total, quality["total_sources"])
        self.assertEqual(f"{counts['OK']} / {total}", quality["completeness_label"])
        self.assertAlmostEqual(counts["OK"] / total, quality["completeness"], places=4)
        if counts["OK"] == total:
            self.assertEqual("OK", quality["status"])
        elif usable == 0:
            self.assertEqual("MISSING", quality["status"])
        else:
            self.assertEqual("PARTIAL", quality["status"])

        non_ok = [name for name in EXPECTED_SOURCES if expected[name] != "OK"]
        self.assertEqual(len(non_ok), len(dataset["warnings"]))
        for name, warning in zip(non_ok, dataset["warnings"]):
            self.assertTrue(
                warning.startswith(f"{name} source is {expected[name].lower()}"),
                f"unexpected warning for {name}: {warning!r}",
            )

    def assert_no_invented_facts(self, dataset: dict[str, Any], names: list[str]) -> None:
        for name in names:
            self.assertEqual(
                EMPTY_DATASET[name],
                dataset[name],
                f"{name} has no usable provider data but the dataset contains values",
            )

    # -- scenarios -----------------------------------------------------------

    def test_all_eight_sources_fresh_and_valid_are_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            dataset = self.build(fixture)

        self.assert_contract(dataset, {name: "OK" for name in EXPECTED_SOURCES})
        self.assertEqual([], dataset["warnings"])
        self.assertEqual(len(MARKET_SYMBOLS), dataset["market"]["coverage"]["available"])
        self.assertEqual(SECTOR_COUNT, len(dataset["sector_rotation"]["sectors"]))
        self.assertEqual(1, len(dataset["events"]["earnings"]))

    def test_selector_candidates_path_is_ok_and_drops_unused_nonfinite_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            dataset = self.build(fixture, candidates="selector")

        self.assert_contract(dataset, {name: "OK" for name in EXPECTED_SOURCES})
        self.assertEqual(["9001"], [row["security_code"] for row in dataset["candidates"]])
        self.assertNotIn("unused_metric", dataset["candidates"][0])

    def test_true_zero_values_are_preserved_as_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            sqlite_dataset = self.build(fixture)
            selector_dataset = self.build(fixture, candidates="selector")

        capital = sqlite_dataset["capital"]
        self.assertEqual(0.0, capital["buying_power"]["cash"])
        self.assertEqual(0.0, capital["margin_usage"]["exposure"])
        self.assertEqual(0.0, capital["capital_state"]["cash_ratio"])
        candidate = sqlite_dataset["candidates"][0]
        self.assertEqual(0.0, candidate["today_score"])
        self.assertEqual(0.0, candidate["reasons"][0]["contribution"])
        self.assertEqual(0.0, selector_dataset["candidates"][0]["total_priority"])
        self.assertEqual(1, selector_dataset["candidates"][0]["rank"])
        self.assertEqual(0.0, sqlite_dataset["portfolio"]["positions"][0]["avg_price"])
        self.assertEqual(0.0, sqlite_dataset["investor_dna"]["environment_fit"]["score"])
        sector = next(row for row in sqlite_dataset["sector_rotation"]["sectors"] if row["id"] == "S00")
        self.assertEqual(0, sector["flow_score"])
        self.assertEqual(0, sector["scores"]["relative_strength"])
        self.assertIsNone(sector["scores"]["breadth"], "null score must stay null, not become zero")

    def test_all_sources_missing_produce_no_invented_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))  # no files written
            dataset = self.build(fixture, fetcher=lambda symbol: {"chart": {"result": [], "error": "synthetic"}})

        self.assert_contract(dataset, {name: "MISSING" for name in EXPECTED_SOURCES})
        self.assertEqual("MISSING", dataset["data_quality"]["status"])
        self.assert_no_invented_facts(dataset, list(EXPECTED_SOURCES))

    def test_mixed_freshness_and_missing_sources(self) -> None:
        old = (TODAY - timedelta(days=10)).isoformat()
        future = (TODAY + timedelta(days=2)).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            write_portfolio(fixture.portfolio, as_of=old)
            write_capital(fixture.capital, snapshot_at=f"{future}T05:00:00+09:00")
            # candidates: no database at all
            write_investor_dna(fixture.investor_dna, as_of=TODAY.isoformat())
            write_events(fixture.events, as_of=old)
            write_watchlist(fixture.watchlist, as_of=None)
            write_sector_history(fixture.sectors, as_of=(SECTOR_AS_OF - timedelta(days=7)).isoformat())
            overrides = {str(spec["symbol"]): [] for spec in list(MARKET_SYMBOLS.values())[:2]}
            dataset = self.build(fixture, fetcher=market_fetcher(overrides))

        self.assert_contract(
            dataset,
            {
                "market": "PARTIAL",
                "portfolio": "STALE",
                "capital": "PARTIAL",
                "candidates": "MISSING",
                "investor_dna": "OK",
                "events": "STALE",
                "watchlist": "PARTIAL",
                "sector_rotation": "STALE",
            },
        )
        self.assertEqual("PARTIAL", dataset["data_quality"]["status"])
        self.assert_no_invented_facts(dataset, ["candidates"])
        # Stale/partial data stays visible with its own declared date.
        self.assertEqual(old, dataset["source_status"][1]["as_of"])

    def test_nonfinite_inputs_in_every_source_never_break_strict_json(self) -> None:
        """Overflowing literals / NaN / inf injected into every provider at once."""
        today = TODAY.isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            write_portfolio(fixture.portfolio, as_of=today, avg_price="1e400")
            write_capital(
                fixture.capital,
                snapshot_at=f"{today}T05:00:00+09:00",
                facts={"total_exposure": float("inf"), "reserve_amount": float("-inf")},
            )
            write_candidates_db(
                fixture.candidates_db,
                generated_at=f"{today}T05:00:00+09:00",
                today_score=float("inf"),
            )
            write_selector(fixture.selector, as_of=today, total_priority="1e400")
            write_investor_dna(fixture.investor_dna, as_of=today, fit="1e400")
            write_events(fixture.events, as_of=today, extra_field="1e400")
            write_watchlist(fixture.watchlist, as_of=today)
            write_sector_history(fixture.sectors, as_of=SECTOR_AS_OF.isoformat(), flow_score_literal="1e400")
            first_symbol = str(next(iter(MARKET_SYMBOLS.values()))["symbol"])
            fetcher = market_fetcher({first_symbol: [100.0, float("inf")]})
            sqlite_dataset = self.build(fixture, fetcher=fetcher)
            selector_dataset = self.build(fixture, candidates="selector", fetcher=fetcher)

        expected = {
            "market": "PARTIAL",
            "portfolio": "MISSING",
            "capital": "PARTIAL",
            "candidates": "PARTIAL",
            "investor_dna": "PARTIAL",
            "events": "MISSING",
            "watchlist": "OK",
            "sector_rotation": "MISSING",
        }
        self.assert_contract(sqlite_dataset, expected)
        self.assert_contract(selector_dataset, expected)
        self.assertIsNone(sqlite_dataset["capital"]["capital_state"]["total_exposure"])
        self.assertIsNone(sqlite_dataset["candidates"][0]["today_score"])
        self.assertIsNone(selector_dataset["candidates"][0]["total_priority"])
        self.assert_no_invented_facts(sqlite_dataset, ["portfolio", "investor_dna", "events", "sector_rotation"])

    def test_nan_and_infinity_constants_are_not_copied(self) -> None:
        today = TODAY.isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            write_portfolio(fixture.portfolio, as_of=today, avg_price="NaN")
            write_investor_dna(fixture.investor_dna, as_of=today, fit="-Infinity")
            write_events(fixture.events, as_of=today, extra_field="NaN")
            write_sector_history(fixture.sectors, as_of=SECTOR_AS_OF.isoformat(), flow_score_literal="Infinity")
            dataset = self.build(fixture)

        self.assert_contract(
            dataset,
            {
                "market": "OK",
                "portfolio": "MISSING",
                "capital": "OK",
                "candidates": "OK",
                "investor_dna": "PARTIAL",
                "events": "MISSING",
                "watchlist": "OK",
                "sector_rotation": "MISSING",
            },
        )

    def test_invalid_metadata_and_undecodable_text_are_reported_not_copied(self) -> None:
        today = TODAY.isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            fixture.capital.unlink()
            write_capital(fixture.capital, snapshot_at=f"{today}T05:00:00+09:00", source=b"\x00\xff")
            fixture.candidates_db.unlink()
            write_candidates_db(
                fixture.candidates_db,
                generated_at=f"{today}T05:00:00+09:00",
                invalid_utf8_status=True,
            )
            write_watchlist(fixture.watchlist, as_of=None, raw=b"## Current Focus\n> as_of: 2026-11-27\n- \xff\xfe\n")
            dataset = self.build(fixture)

        self.assert_contract(
            dataset,
            {
                "market": "OK",
                "portfolio": "OK",
                "capital": "PARTIAL",
                "candidates": "PARTIAL",
                "investor_dna": "OK",
                "events": "OK",
                "watchlist": "MISSING",
                "sector_rotation": "OK",
            },
        )
        self.assertIsNone(dataset["capital"]["capital_state"]["source"])
        self.assertIsNone(dataset["candidates"][0]["status"])
        self.assert_no_invented_facts(dataset, ["watchlist"])

    def test_dataset_is_deterministic_for_identical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Fixture(Path(temp_dir))
            fixture.write_all_fresh()
            first = self.build(fixture)
            second = self.build(fixture)
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True, allow_nan=False),
            json.dumps(second, ensure_ascii=False, sort_keys=True, allow_nan=False),
        )
        self.assertEqual(deepcopy(first), second)


if __name__ == "__main__":
    unittest.main()
