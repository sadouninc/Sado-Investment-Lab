import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.sora_recovery_pickup import discover_sora_pickup


def test_actual_writer_event_is_accepted_only_as_readonly_candidate():
    workflow = Path('.github/workflows/sora-recovery-control-plane.yml').read_text()
    line = next(line.strip() for line in workflow.splitlines() if line.strip().startswith('event="'))
    program = re.search(r"'([^']+)'", line).group(1)
    command = ['jq', '-nc']
    values = {'work_ref': 'issue:859', 'lease': 'lease-' + 'a' * 32,
              'assigned': '2026-10-12T08:00:00Z', 'expires': '2026-10-12T09:30:00Z',
              'source': 'scheduled_pull'}
    for key, value in values.items():
        command += ['--arg', key, value]
    command += ['--argjson', 'writer_run_id', '38000000000', program]
    event = subprocess.check_output(command, text=True).strip()
    assert json.loads(event)['writer_run_id'] == 38000000000
    comment = {'id': 123, 'user': {'login': 'github-actions[bot]'},
               'body': '<!-- AUTO_ROUTER_DISPATCH lease_id=' + values['lease']
                       + ' executor=SORA target_issue=859 -->\n' + event}
    result = discover_sora_pickup(issue_number=859, comments=[comment],
                                 now=datetime(2026, 10, 12, 8, 2, tzinfo=timezone.utc))
    assert result['status'] == 'PICKUP_CANDIDATE'
    assert result['write_performed'] is False
    assert result['candidate']['writer_run_id'] == 38000000000
