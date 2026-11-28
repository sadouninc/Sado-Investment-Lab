"""#982: strict-JSON integration contract across all eight Morning Dataset sources.

Every provider is driven by synthetic fixtures only (temporary files, synthetic
SQLite, an injected market fetcher). No live, private or networked data is read.

The contract checked here is the one the strict validator (#972 / PR #976)
relies on: whatever each provider returns, ``build_dataset_from_providers``
must produce a dataset that

* reports every one of the eight canonical sources exactly once,
* keeps quality counts and warnings consistent with ``source_status``,
* serializes with ``json.dumps(..., allow_nan=False)``, and
* does not invent facts for missing or malformed inputs.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.morning_dataset.generator import build_dataset_from_providers
from scripts.morning_dataset.providers import (
    EXPECTED_SOURCES,
    CandidateSelectorProvider,
    CandidatesProvider,
    CapitalProvider,
    EventsProvider,
    JsonFileProvider,
    MARKET_SYMBOLS,
    MarketProvider,
    PortfolioProvider,
    SectorRotationProvider,
    WatchlistProvider,
)
from scripts.morning_dataset.validator import validate_dataset


# Thursday; the previous Japan market business day is 2026-08-12.
REPORT_DATE = date(2026, 8, 13)
AS_OF = "2026-08-13"
SECTOR_AS_OF = "2026-08-12"
SECTOR_COUNT = 2

CAPITAL_SCHEMA = """
CREATE TABLE capital_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    cash_buying_power REAL,
    margin_buying_power REAL,
    cash_ratio REAL,
    margin_exposure REAL,
    margin_ratio REAL,
    total_exposure REAL,
    reserve_amount REAL,
    source TEXT,
    source_version TEXT
);
"""

CANDIDATES_SCHEMA = """
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    security_code TEXT,
    horizon TEXT,
    universe_state TEXT,
    long_score REAL,
    today_score REAL,
    risk_score REAL,
    personal_fit REAL,
    capital_feasibility REAL,
    rotation_score REAL,
    rank INTEGER,
    status TEXT,
    confidence REAL,
    model_name TEXT,
    model_version TEXT
);
CREATE TABLE candidate_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    factor_type TEXT,
    factor_key TEXT,
    value_numeric REAL,
    value_text TEXT,
    contribution REAL,
    polarity TEXT,
    source_reference TEXT
);
"""

NORMAL_CAPITAL_ROW = (
    f"{AS_OF}T08:30:00+09:00", 1_200_000, 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "synthetic", "v1",
)


def market_chart(closes: list) -> dict:
    base = int(datetime(2026, 8, 11, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [{
                "timestamp": [base + 86400 * i for i in range(len(closes))],
                "indicators": {"quote": [{"close": closes}]},
            }],
            "error": None,
        }
    }


def sector_row(entity_id: str, *, flow_score=61.5, as_of: str = SECTOR_AS_OF) -> dict:
    return {
        "kind": "SECTOR",
        "id": entity_id,
        "name": entity_id.upper(),
        "as_of": as_of,
        "state": "WARMING",
        "previous_state": "COLD",
        "state_since": as_of,
        "flow_score": flow_score,
        "scores": {
            "relative_strength": 12.0,
            "activity": 55.0,
            "breadth": None,
            "heat": 40.0,
            "acceleration": 70.0,
        },
        "data_completeness": "OK",
        "evidence": ["fixture"],
    }


class Fixtures:
    """Write one synthetic input per source into a temporary directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._counter = 0

    def unique(self, name: str) -> Path:
        # Each write gets its own file so an override is never clobbered by a
        # default fixture written later for the same source.
        self._counter += 1
        stem, dot, suffix = name.partition(".")
        return self.root / f"{stem}-{self._counter}{dot}{suffix}"

    # --- writers -----------------------------------------------------------

    def json(self, name: str, payload) -> Path:
        path = self.unique(name)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def text(self, name: str, text: str) -> Path:
        path = self.unique(name)
        path.write_text(text, encoding="utf-8")
        return path

    def portfolio(self, position_extra: dict | None = None) -> Path:
        position = {"security_code": "4063", "security_name": "信越化学", "position_type": "cash", "quantity": 100}
        position.update(position_extra or {})
        return self.json("current.json", {
            "as_of": AS_OF,
            "verification_status": "VERIFIED",
            "base_snapshot": f"verified-{AS_OF}",
            "positions": [position],
        })

    def capital(self, row: tuple | None = NORMAL_CAPITAL_ROW) -> Path:
        path = self.unique("capital.db")
        connection = sqlite3.connect(path)
        try:
            connection.executescript(CAPITAL_SCHEMA)
            if row is not None:
                connection.execute(
                    """
                    INSERT INTO capital_snapshots (
                        snapshot_at, cash_buying_power, margin_buying_power,
                        cash_ratio, margin_exposure, margin_ratio,
                        total_exposure, reserve_amount, source, source_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
            connection.commit()
        finally:
            connection.close()
        return path

    def candidate_selector(self, candidate_extra: dict | None = None) -> Path:
        candidate = {
            "security_code": "6622",
            "company_name": "ダイヘン",
            "research_status": "NOT_STARTED",
            "total_priority": 72.5,
            "rank": 1,
            "owner_pick": False,
            "candidate_sources": ["SYNTHETIC"],
            "selection_reason": "synthetic fixture",
            "last_researched_at": None,
        }
        candidate.update(candidate_extra or {})
        return self.json("candidate-selector.json", {
            "as_of": AS_OF,
            "ranked_candidates": [
                candidate,
                {"security_code": None, "company_name": "未解決テーマ", "research_status": "NOT_STARTED"},
            ],
        })

    def candidates_db(self, today_score: float = 80.0) -> Path:
        path = self.unique("history.db")
        connection = sqlite3.connect(path)
        try:
            connection.executescript(CANDIDATES_SCHEMA)
            cursor = connection.execute(
                """
                INSERT INTO candidates (
                    generated_at, security_code, horizon, universe_state,
                    long_score, today_score, risk_score, personal_fit,
                    capital_feasibility, rotation_score, rank, status,
                    confidence, model_name, model_version
                ) VALUES (?, '6622', 'SHORT_SWING', 'ACTIVE', 70, ?, 20, 80, 90, 60, 1, 'WATCH', 0.8, 'candidate-v1', '1')
                """,
                (f"{AS_OF}T08:00:00+09:00", today_score),
            )
            connection.execute(
                "INSERT INTO candidate_factors (candidate_id, factor_type, factor_key, value_text, polarity) "
                "VALUES (?, 'positive', 'theme', 'synthetic reason', 'positive')",
                (cursor.lastrowid,),
            )
            connection.commit()
        finally:
            connection.close()
        return path

    def investor_dna(self, extra_text: str = "") -> Path:
        body = json.dumps(
            {"as_of": AS_OF, "native_dna": {"type": "MOMENTUM"}, "environment_fit": {"score": 58}},
            ensure_ascii=False,
        )
        return self.text("investor-dna.json", body[:-1] + extra_text + "}")

    def events(self, *, empty: bool = False, empty_confirmed: bool = True, extra_text: str = "") -> Path:
        events = {
            "earnings": [] if empty else [{"title": "Synthetic earnings", "date": AS_OF, "security_code": "9999"}],
            "economic": [] if empty else [{"title": "Synthetic indicator", "scheduled_at": f"{AS_OF}T21:30:00+09:00"}],
            "policy": [],
            "market_calendar": [],
            "company": [],
        }
        payload = {
            "as_of": AS_OF,
            "source": "synthetic",
            "coverage": {key: True for key in events},
            "events": events,
        }
        if empty and empty_confirmed:
            payload["empty_confirmed"] = True
        body = json.dumps(payload, ensure_ascii=False)
        return self.text("calendar.json", body[:-1] + extra_text + "}")

    def watchlist(self, as_of: str = AS_OF) -> Path:
        return self.text("Current_Status.md", f"""# Current Status
> 最終更新: {as_of}

## Current Focus
> as_of: {as_of}

- ダイヘンの受注動向
- 送電網投資

## TODO
- [ ] synthetic
""")

    def sector_history(self, rows: list[dict] | None = None, raw_lines: list[str] | None = None) -> Path:
        rows = rows if rows is not None else [sector_row("sector:a"), sector_row("sector:b")]
        lines = [json.dumps(row, ensure_ascii=False) for row in rows] + list(raw_lines or [])
        return self.text("sector-history.jsonl", "\n".join(lines) + "\n")

    # --- provider sets -----------------------------------------------------

    def providers(self, *, alternate_candidates: bool = False, market_fetcher=None, **overrides) -> list:
        fetcher = market_fetcher or (lambda symbol: market_chart([100.0, 102.0]))
        providers = {
            "market": MarketProvider(fetcher=fetcher),
            "portfolio": PortfolioProvider(self.portfolio(), today=REPORT_DATE),
            "capital": CapitalProvider(self.capital(), today=REPORT_DATE),
            "candidates": (
                CandidatesProvider(self.candidates_db(), today=REPORT_DATE)
                if alternate_candidates
                else CandidateSelectorProvider(self.candidate_selector(), today=REPORT_DATE)
            ),
            "investor_dna": JsonFileProvider("investor_dna", self.investor_dna()),
            "events": EventsProvider(self.events(), today=REPORT_DATE),
            "watchlist": WatchlistProvider(self.watchlist(), today=REPORT_DATE),
            "sector_rotation": SectorRotationProvider(
                path=self.sector_history(), expected_count=SECTOR_COUNT, report_date=REPORT_DATE
            ),
        }
        for name, provider in overrides.items():
            if provider is None:
                del providers[name]
            else:
                providers[name] = provider
        return list(providers.values())


class MorningProviderIntegrationContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixtures(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- helpers -------------------------------------------------------------

    def build(self, providers: list) -> dict:
        dataset = build_dataset_from_providers(providers, as_of=REPORT_DATE)
        self.assert_contract(dataset)
        return dataset

    def assert_contract(self, dataset: dict) -> None:
        # Strict, finite JSON: the public serialization contract.
        text = json.dumps(dataset, ensure_ascii=False, allow_nan=False)
        self.assertEqual(dataset, json.loads(text))
        # Every canonical source appears exactly once, in canonical order.
        names = [row["name"] for row in dataset["source_status"]]
        self.assertEqual(list(EXPECTED_SOURCES), names)
        # Quality counts agree with source_status.
        statuses = [row["status"] for row in dataset["source_status"]]
        quality = dataset["data_quality"]
        counts = {status: statuses.count(status) for status in ("OK", "PARTIAL", "STALE", "MISSING")}
        self.assertEqual(counts, quality["source_counts"])
        self.assertEqual(len(EXPECTED_SOURCES), quality["total_sources"])
        self.assertEqual(counts["OK"], quality["ok_sources"])
        self.assertEqual(counts["OK"] + counts["PARTIAL"] + counts["STALE"], quality["usable_sources"])
        self.assertEqual(f"{counts['OK']} / {len(EXPECTED_SOURCES)}", quality["completeness_label"])
        # One warning per non-OK source, naming that source.
        non_ok = [row["name"] for row in dataset["source_status"] if row["status"] != "OK"]
        self.assertEqual(len(non_ok), len(dataset["warnings"]))
        for name, warning in zip(non_ok, dataset["warnings"]):
            self.assertTrue(warning.startswith(f"{name} source is "), warning)
        # Every non-OK source explains itself.
        for row in dataset["source_status"]:
            if row["status"] != "OK":
                self.assertTrue(row["reason"], row)
        # The dataset is accepted by the validator on this checkout.
        validate_dataset(dataset)

    def status(self, dataset: dict, name: str) -> str:
        return next(row for row in dataset["source_status"] if row["name"] == name)["status"]

    def statuses(self, dataset: dict) -> dict[str, str]:
        return {row["name"]: row["status"] for row in dataset["source_status"]}

    # --- normal --------------------------------------------------------------

    def test_all_eight_sources_ok_with_selector_candidates(self) -> None:
        dataset = self.build(self.fx.providers())
        self.assertEqual({name: "OK" for name in EXPECTED_SOURCES}, self.statuses(dataset))
        self.assertEqual("OK", dataset["data_quality"]["status"])
        self.assertEqual([], dataset["warnings"])
        # Facts are carried, not invented.
        self.assertIsNone(dataset["capital"]["cash_available"])
        self.assertEqual(["6622"], [row["security_code"] for row in dataset["candidates"]])
        self.assertEqual(len(MARKET_SYMBOLS), dataset["market"]["coverage"]["available"])
        self.assertEqual(SECTOR_COUNT, len(dataset["sector_rotation"]["sectors"]))

    def test_all_eight_sources_ok_with_alternate_sqlite_candidates(self) -> None:
        dataset = self.build(self.fx.providers(alternate_candidates=True))
        self.assertEqual({name: "OK" for name in EXPECTED_SOURCES}, self.statuses(dataset))
        self.assertEqual("6622", dataset["candidates"][0]["security_code"])
        self.assertEqual("synthetic reason", dataset["candidates"][0]["reasons"][0]["value_text"])

    # --- missing / mixed -----------------------------------------------------

    def test_no_providers_configured_is_all_missing(self) -> None:
        dataset = self.build([])
        self.assertEqual({name: "MISSING" for name in EXPECTED_SOURCES}, self.statuses(dataset))
        self.assertEqual("MISSING", dataset["data_quality"]["status"])
        for row in dataset["source_status"]:
            self.assertEqual("provider not configured", row["reason"])

    def test_missing_inputs_are_missing_not_fabricated(self) -> None:
        root = self.fx.root
        dataset = self.build(self.fx.providers(
            portfolio=PortfolioProvider(root / "absent.json", today=REPORT_DATE),
            capital=CapitalProvider(root / "absent.db", today=REPORT_DATE),
            candidates=CandidateSelectorProvider(root / "absent-selector.json", today=REPORT_DATE),
            investor_dna=JsonFileProvider("investor_dna", root / "absent-dna.json"),
            events=EventsProvider(root / "absent-calendar.json", today=REPORT_DATE),
            watchlist=WatchlistProvider(root / "absent.md", today=REPORT_DATE),
            sector_rotation=SectorRotationProvider(
                path=root / "absent.jsonl", expected_count=SECTOR_COUNT, report_date=REPORT_DATE
            ),
            market_fetcher=lambda symbol: (_ for _ in ()).throw(TimeoutError("synthetic")),
        ))
        self.assertEqual({name: "MISSING" for name in EXPECTED_SOURCES}, self.statuses(dataset))
        self.assertEqual("MISSING", dataset["data_quality"]["status"])
        # Absent sources keep the empty schema rather than invented values.
        self.assertIsNone(dataset["capital"]["buying_power"])
        self.assertIsNone(dataset["candidates"])
        self.assertIsNone(dataset["sector_rotation"])

    def test_mixed_ok_partial_stale_missing(self) -> None:
        failing = MARKET_SYMBOLS["vix"]["symbol"]

        def market(symbol: str) -> dict:
            if symbol == failing:
                raise TimeoutError("synthetic")
            return market_chart([100.0, 101.0])

        dataset = self.build(self.fx.providers(
            market_fetcher=market,
            watchlist=WatchlistProvider(self.fx.watchlist(as_of="2026-08-01"), today=REPORT_DATE),
            capital=CapitalProvider(self.fx.root / "absent.db", today=REPORT_DATE),
            events=EventsProvider(self.fx.events(empty=True, empty_confirmed=False), today=REPORT_DATE),
        ))
        statuses = self.statuses(dataset)
        self.assertEqual("PARTIAL", statuses["market"])
        self.assertEqual("STALE", statuses["watchlist"])
        self.assertEqual("MISSING", statuses["capital"])
        # An unconfirmed empty calendar is not "nothing scheduled".
        self.assertEqual("MISSING", statuses["events"])
        for name in ("portfolio", "candidates", "investor_dna", "sector_rotation"):
            self.assertEqual("OK", statuses[name], name)
        self.assertEqual("PARTIAL", dataset["data_quality"]["status"])
        # Partial/stale data is preserved alongside its status.
        self.assertNotIn("vix", dataset["market"]["indices"])
        self.assertEqual("送電網投資", dataset["watchlist"]["items"][1]["text"])

    def test_verified_empty_event_day_is_ok(self) -> None:
        dataset = self.build(self.fx.providers(
            events=EventsProvider(self.fx.events(empty=True), today=REPORT_DATE),
        ))
        self.assertEqual("OK", self.status(dataset, "events"))
        self.assertEqual([], dataset["events"]["earnings"])

    # --- true zero ---------------------------------------------------------------

    def test_true_zero_values_are_kept_and_not_turned_into_changes(self) -> None:
        zero_capital = (f"{AS_OF}", 0, 0.0, 0.0, 0, 0.0, 0, 0, "synthetic", "v1")
        dataset = self.build(self.fx.providers(
            capital=CapitalProvider(self.fx.capital(zero_capital), today=REPORT_DATE),
            market_fetcher=lambda symbol: market_chart([0.0, 5.0]),
        ))
        self.assertEqual("OK", self.status(dataset, "capital"))
        self.assertEqual(0, dataset["capital"]["buying_power"]["cash"])
        self.assertEqual(0, dataset["capital"]["target_reserve"])
        nikkei = dataset["market"]["indices"]["nikkei_225"]
        self.assertEqual(0.0, nikkei["previous_close"])
        self.assertIsNone(nikkei["change"])
        self.assertIsNone(nikkei["change_pct"])

    # --- non-finite and malformed input, one source at a time ---------------------

    def assert_source_not_ok_and_strict(self, providers: list, name: str) -> dict:
        dataset = self.build(providers)
        self.assertNotEqual("OK", self.status(dataset, name), name)
        # Every other source remains OK: the failure is isolated.
        for other, status in self.statuses(dataset).items():
            if other != name:
                self.assertEqual("OK", status, f"{other} changed while injecting into {name}")
        return dataset

    def test_market_non_finite_close_is_isolated(self) -> None:
        failing = MARKET_SYMBOLS["nikkei_225"]["symbol"]
        for bad in (float("nan"), float("inf")):
            with self.subTest(close=bad):
                def market(symbol: str, bad=bad) -> dict:
                    return market_chart([100.0, bad]) if symbol == failing else market_chart([100.0, 101.0])

                dataset = self.assert_source_not_ok_and_strict(self.fx.providers(market_fetcher=market), "market")
                self.assertNotIn("nikkei_225", dataset["market"]["indices"])

    def test_portfolio_non_finite_numbers_are_isolated(self) -> None:
        for literal in ("1e400", "NaN", "-Infinity"):
            with self.subTest(literal=literal):
                path = self.fx.portfolio()
                text = path.read_text(encoding="utf-8").replace('"quantity": 100', f'"quantity": 100, "average_price": {literal}')
                path.write_text(text, encoding="utf-8")
                self.assert_source_not_ok_and_strict(
                    self.fx.providers(portfolio=PortfolioProvider(path, today=REPORT_DATE)), "portfolio"
                )

    def test_capital_non_finite_facts_and_blob_metadata_are_isolated(self) -> None:
        rows = {
            "inf buying power": (AS_OF, float("inf"), 3_000_000, 0.24, None, None, None, None, "synthetic", "v1"),
            "text ratio": (AS_OF, 100, 200, "high", None, None, None, None, "synthetic", "v1"),
            "blob metadata": (AS_OF, 100, 200, None, None, None, None, None, b"\x00blob", "v1"),
        }
        for label, row in rows.items():
            with self.subTest(case=label):
                path = self.fx.capital(row)
                dataset = self.assert_source_not_ok_and_strict(
                    self.fx.providers(capital=CapitalProvider(path, today=REPORT_DATE)), "capital"
                )
                self.assertIsNone(dataset["capital"]["cash_available"])

    def test_candidate_non_finite_priority_is_isolated(self) -> None:
        for literal in ("1e400", "NaN"):
            with self.subTest(literal=literal):
                path = self.fx.candidate_selector()
                text = path.read_text(encoding="utf-8").replace('"total_priority": 72.5', f'"total_priority": {literal}')
                path.write_text(text, encoding="utf-8")
                self.assert_source_not_ok_and_strict(
                    self.fx.providers(candidates=CandidateSelectorProvider(path, today=REPORT_DATE)), "candidates"
                )

    def test_alternate_sqlite_candidate_non_finite_score_does_not_break_strict_json(self) -> None:
        path = self.fx.candidates_db(today_score=float("inf"))
        dataset = self.build(self.fx.providers(candidates=CandidatesProvider(path, today=REPORT_DATE)))
        # Whatever status the legacy provider reports, the value must not leak as inf.
        self.assertNotIn("Infinity", json.dumps(dataset["candidates"], ensure_ascii=False, allow_nan=False))

    def test_investor_dna_non_finite_numbers_are_isolated(self) -> None:
        for literal in ("1e400", "NaN", "Infinity"):
            with self.subTest(literal=literal):
                path = self.fx.investor_dna(extra_text=f', "score": {literal}')
                self.assert_source_not_ok_and_strict(
                    self.fx.providers(investor_dna=JsonFileProvider("investor_dna", path)), "investor_dna"
                )

    def test_events_non_finite_numbers_are_isolated(self) -> None:
        for literal in ("1e400", "NaN", "-Infinity"):
            with self.subTest(literal=literal):
                path = self.fx.events(extra_text=f', "score": {literal}')
                self.assert_source_not_ok_and_strict(
                    self.fx.providers(events=EventsProvider(path, today=REPORT_DATE)), "events"
                )

    def test_sector_rotation_non_finite_scores_are_isolated(self) -> None:
        for bad_line in (
            json.dumps(sector_row("sector:b"))[:-1].replace('"flow_score": 61.5', '"flow_score": NaN') + "}",
            json.dumps(sector_row("sector:b")).replace('"flow_score": 61.5', '"flow_score": 1e400'),
        ):
            with self.subTest(line=bad_line[:40]):
                path = self.fx.sector_history(rows=[sector_row("sector:a")], raw_lines=[bad_line])
                self.assert_source_not_ok_and_strict(
                    self.fx.providers(sector_rotation=SectorRotationProvider(
                        path=path, expected_count=SECTOR_COUNT, report_date=REPORT_DATE
                    )),
                    "sector_rotation",
                )

    def test_every_source_malformed_at_once_still_builds_strict_dataset(self) -> None:
        def market(symbol: str) -> dict:
            return market_chart([100.0, float("nan")])

        portfolio = self.fx.portfolio()
        portfolio.write_text(portfolio.read_text(encoding="utf-8").replace('"quantity": 100', '"quantity": 1e400'), encoding="utf-8")
        selector = self.fx.candidate_selector()
        selector.write_text(selector.read_text(encoding="utf-8").replace('"total_priority": 72.5', '"total_priority": NaN'), encoding="utf-8")
        dataset = self.build(self.fx.providers(
            market_fetcher=market,
            portfolio=PortfolioProvider(portfolio, today=REPORT_DATE),
            capital=CapitalProvider(
                self.fx.capital((AS_OF, float("inf"), float("-inf"), None, None, None, None, None, b"blob", None)),
                today=REPORT_DATE,
            ),
            candidates=CandidateSelectorProvider(selector, today=REPORT_DATE),
            investor_dna=JsonFileProvider("investor_dna", self.fx.investor_dna(extra_text=', "score": NaN')),
            events=EventsProvider(self.fx.events(extra_text=', "score": 1e400'), today=REPORT_DATE),
            sector_rotation=SectorRotationProvider(
                path=self.fx.sector_history(raw_lines=['{"kind": "SECTOR", "flow_score": Infinity}']),
                expected_count=SECTOR_COUNT,
                report_date=REPORT_DATE,
            ),
        ))
        statuses = self.statuses(dataset)
        for name in ("market", "portfolio", "capital", "candidates", "investor_dna", "events", "sector_rotation"):
            self.assertNotEqual("OK", statuses[name], name)
        # The watchlist (Markdown, no JSON numbers) is unaffected.
        self.assertEqual("OK", statuses["watchlist"])
        self.assertNotEqual("OK", dataset["data_quality"]["status"])


if __name__ == "__main__":
    unittest.main()
