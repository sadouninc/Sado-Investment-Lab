担当: ♦️ソラ
種別: Implementation / Test Handoff
Status: REVIEW / VERIFY

#312 PR1 implements the read-only Home / Investment OS Map entry.

- 9-stage OS Map config: `.github/pages/os-map-v1.json`
- deterministic renderer: `.github/pages/home_os_map.py`
- Home shell template: `.github/pages/home-os-map-template.md`
- rendered Home: `.github/pages/home.md`
- contract tests: `tests/test_home_os_map.py`
- shared #320 semantic classes/tokens are reused by the Home shell

Safety:
- no Canonical Research / Decision / Portfolio / Trade mutation
- no BUY/SELL or priority scoring
- unknown destinations fail closed
- existing destination URLs remain unchanged
- Issue #79 untouched

Broadcast checked through: comment_id=5246936719 — VERIFIED
