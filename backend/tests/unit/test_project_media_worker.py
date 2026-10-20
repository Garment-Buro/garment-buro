import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "option,value",
    [
        ("--max-items", "0"),
        ("--max-items", "1001"),
        ("--poll-seconds", "0"),
        ("--poll-seconds", "nan"),
        ("--poll-seconds", "inf"),
        ("--unattached-hours", "-1"),
        ("--stale-upload-hours", "nan"),
    ],
)
def test_worker_rejects_invalid_batch_before_connecting(option, value):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.reconcile_project_media", "--once", option, value],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
