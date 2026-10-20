from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_importing_asgi_entrypoint_does_not_open_connections_or_create_legacy_files(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT"}}
    environment.update(APP_ENV="test", PYTHONPATH=str(backend), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import importlib.abc
import socket
import sys
from pathlib import Path

def connection_attempt(*args, **kwargs):
    raise AssertionError('Import must not connect to external services')

socket.socket.connect = connection_attempt
class RetiredModuleBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *_args):
        retired = {'main', 'cdek_client', 'payments', 'email_service', 'image_optimization', 'sqladmin', 'yookassa', 'aiosqlite'}
        if fullname.split('.')[0] in retired or fullname.startswith('app.modules.catalog.migration'):
            raise AssertionError('Runtime depends on retired/import-only module: ' + fullname)
sys.meta_path.insert(0, RetiredModuleBlocker())
from app.main import app
print(json.dumps({
    'legacy_imported': 'main' in sys.modules,
    'files': sorted(str(path) for path in Path.cwd().iterdir()),
    'database_started': app.state.database._engine is not None,
}))
""",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout.splitlines()[-1])
    assert state == {"legacy_imported": False, "files": [], "database_started": False}
