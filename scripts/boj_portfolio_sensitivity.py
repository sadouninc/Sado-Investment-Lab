#!/usr/bin/env python3
"""BOJ Portfolio Sensitivity - Owner: 🌅アサヒ"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class PortfolioSensitivityEngine:
    """BOJ sensitivity mapping engine"""
    
    def __init__(self, base_dir=None):
        self.base = Path(base_dir or Path(__file__).parent.parent)
    
    def read_holdings_file(self):
        """Read portfolio file"""
        path = self.base / "data/portfolio/current.json"
        with open(path) as f:
            return json.load(f).get("holdings", [])
    
    def read_company_file(self, code):
        """Read company sensitivity file"""
        path = self.base / f"data/research/boj_sensitivity/{code}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)
    
    def build_unknown_record(self, code, name, ptype="LONG"):
        """Build unknown sensitivity record"""
        return {
            "ticker": code, "name": name,
            "rate_sensitivity": "UNKNOWN",
            "yen_sensitivity": "UNKNOWN",
            "energy_input_sensitivity": "UNKNOWN",
            "valuation_duration": "UNKNOWN",
            "balance_sheet_rate_risk": "UNKNOWN",
            "boj_risk_action": "HOLD",
            "evidence_refs": [],
            "confidence": "LOW",
            "position_type": ptype,
            "notes": "No evidence available"
        }
    
    def compute_action_level(self, record, signal):
        """Compute action from sensitivity"""
        if record["rate_sensitivity"] == "UNKNOWN":
            return "HOLD"
        if signal == "GREEN":
            return "HOLD"
        
        high_count = 0
        for field in ["rate_sensitivity", "valuation_duration", "balance_sheet_rate_risk"]:
            if record.get(field) == "HIGH":
                high_count += 1
        
        pos = record.get("position_type", "LONG")
        
        if pos == "SHORT":
            if signal == "RED" and high_count >= 2:
                return "SHORT_THESIS_REVIEW"
            if signal == "ORANGE" and high_count >= 2:
                return "WATCH"
            return "HOLD"
        
        if signal == "RED":
            if high_count >= 2:
                return "REDUCE_CANDIDATE"
            if high_count >= 1:
                return "WATCH"
        elif signal == "ORANGE" and high_count >= 2:
            return "WATCH"
        
        return "HOLD"
    
    def process_portfolio(self, signal_state):
        """Process all holdings"""
        holdings = self.read_holdings_file()
        output = []
        counters = {
            "total": len(holdings),
            "high_sens": 0,
            "watch": 0,
            "reduce": 0,
            "exit": 0,
            "unknown": 0
        }
        
        for item in holdings:
            code = item.get("ticker") or item.get("code", "")
            name = item.get("name", "")
            ptype = item.get("position_type", "LONG")
            
            rec = self.read_company_file(code)
            if not rec:
                rec = self.build_unknown_record(code, name, ptype)
                counters["unknown"] += 1
            
            action = self.compute_action_level(rec, signal_state)
            rec["boj_risk_action"] = action
            
            if rec["rate_sensitivity"] == "HIGH":
                counters["high_sens"] += 1
            
            if action == "WATCH":
                counters["watch"] += 1
            elif action == "REDUCE_CANDIDATE":
                counters["reduce"] += 1
            elif action == "EXIT_REVIEW":
                counters["exit"] += 1
            
            output.append(rec)
        
        return {
            "boj_signal_state": signal_state,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "holdings": output,
            "summary": {
                "total_holdings": counters["total"],
                "high_sensitivity_count": counters["high_sens"],
                "watch_count": counters["watch"],
                "reduce_candidate_count": counters["reduce"],
                "exit_review_count": counters["exit"],
                "unknown_count": counters["unknown"]
            }
        }
    
    def extract_candidates(self, signal_state):
        """Extract review candidates"""
        result = self.process_portfolio(signal_state)
        target_actions = ["WATCH", "REDUCE_CANDIDATE", "EXIT_REVIEW", "SHORT_THESIS_REVIEW"]
        candidates = [h for h in result["holdings"] if h["boj_risk_action"] in target_actions]
        
        order_map = {
            "EXIT_REVIEW": 1,
            "REDUCE_CANDIDATE": 2,
            "WATCH": 3,
            "SHORT_THESIS_REVIEW": 4
        }
        candidates.sort(key=lambda x: order_map.get(x["boj_risk_action"], 99))
        return candidates
    
    def write_output_file(self, signal_state, dest=None):
        """Write output to file"""
        if not dest:
            dest = self.base / "data/boj/portfolio_sensitivity.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        result = self.process_portfolio(signal_state)
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return dest


def read_signal_file(base_dir=None):
    """Read signal state file"""
    base = Path(base_dir or Path(__file__).parent.parent)
    path = base / "data/boj/signal_state.json"
    if not path.exists():
        return "ORANGE"
    with open(path) as f:
        return json.load(f).get("signal_state", "ORANGE")


def generate_full_report(signal_state, base_dir=None):
    """Generate complete report"""
    engine = PortfolioSensitivityEngine(base_dir)
    mapping = engine.process_portfolio(signal_state)
    candidates = engine.extract_candidates(signal_state)
    
    return {
        "signal_state": signal_state,
        "portfolio_mapping": mapping,
        "review_candidates": candidates,
        "requires_attention": len(candidates) > 0
    }


def main():
    import sys
    engine = PortfolioSensitivityEngine()
    state = sys.argv[1] if len(sys.argv) > 1 else "ORANGE"
    result = engine.process_portfolio(state)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

