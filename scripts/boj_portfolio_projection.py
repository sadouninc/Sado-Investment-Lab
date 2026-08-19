#!/usr/bin/env python3
"""BOJ Portfolio Check - Read-Only - Owner: 🌅アサヒ"""
import json
from pathlib import Path


class CheckProjector:
    """Projects BOJ risk to portfolio check"""
    
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).parent.parent)
    
    def fetch_sensitivity(self):
        """Fetch sensitivity file"""
        p = self.root / "data/boj/portfolio_sensitivity.json"
        return json.load(open(p)) if p.exists() else None
    
    def fetch_signal(self):
        """Fetch signal file"""
        p = self.root / "data/boj/signal_state.json"
        return json.load(open(p)) if p.exists() else {"signal_state": "ORANGE"}
    
    def tier_a_filter(self, records):
        """Tier A: immediate"""
        out = []
        for r in records:
            act = r.get("boj_risk_action", "HOLD")
            rs = r.get("rate_sensitivity", "")
            vd = r.get("valuation_duration", "")
            if act in ["REDUCE_CANDIDATE", "EXIT_REVIEW"] and rs == "HIGH" and vd == "HIGH":
                out.append(r)
        return out
    
    def tier_b_filter(self, records):
        """Tier B: watch"""
        return [r for r in records if r.get("boj_risk_action") == "WATCH"]
    
    def tier_c_filter(self, records):
        """Tier C: monitor"""
        out = []
        for r in records:
            if r.get("boj_risk_action") == "HOLD":
                rs = r.get("rate_sensitivity", "")
                if rs in ["LOW", "MEDIUM"]:
                    out.append(r)
        return out
    
    def short_filter(self, records):
        """Short lane"""
        return [r for r in records if r.get("position_type") == "SHORT"]
    
    def build_output(self):
        """Build projection output"""
        sens = self.fetch_sensitivity()
        sig = self.fetch_signal()
        
        if not sens:
            return {
                "available": False,
                "reason": "No sensitivity data"
            }
        
        recs = sens.get("holdings", [])
        
        ta = self.tier_a_filter(recs)
        tb = self.tier_b_filter(recs)
        tc = self.tier_c_filter(recs)
        sl = self.short_filter(recs)
        
        return {
            "available": True,
            "signal": sig.get("signal_state", "UNKNOWN"),
            "time": sens.get("timestamp"),
            "tiers": {
                "a": {"count": len(ta), "items": ta, "desc": "Immediate review"},
                "b": {"count": len(tb), "items": tb, "desc": "Watch"},
                "c": {"count": len(tc), "items": tc, "desc": "Monitor"},
                "short": {"count": len(sl), "items": sl, "desc": "Short review"}
            },
            "notice": "READ-ONLY. No auto-trades. Owner approval required."
        }


def run():
    """Run projector"""
    proj = CheckProjector()
    out = proj.build_output()
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()

