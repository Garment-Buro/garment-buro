#!/usr/bin/env python3
"""Exercise real vhosts and the release gate controller on owned loopback HTTPS.

Requires nginx and openssl; never reloads a system service or calls public hosts.
Only listeners, fixture upstreams, certificate, logging and control paths change.
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = "a" * 40 + "-" + "b" * 32
OTHER = "c" * 40 + "-" + "d" * 32
spec = importlib.util.spec_from_file_location(
    "privacy_fixture", Path(__file__).with_name("verify-nginx-privacy.py")
)
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class Upstream(BaseHTTPRequestHandler):
    calls = 0

    def do_GET(self):
        type(self).calls += 1
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    do_POST = do_GET

    def log_message(self, *_args):
        pass


def managed_hosts(source: str) -> dict[str, str]:
    hosts = {}
    for block in re.split(r"(?m)^server\s*\{", source)[1:]:
        if "listen 443" not in block:
            continue
        names = re.search(r"server_name\s+([^;]+);", block)[1].split()
        if names == ["widget.garment-buro.ru"]:
            assert "maintenance.conf" not in block, (
                "Widget has a separate release lifecycle"
            )
            continue
        expected = "development" if names == ["dev.garment-buro.ru"] else "production"
        assert block.count("include /etc/nginx/garment-buro/maintenance.conf;") == 1, (
            names
        )
        assert f"set $garment_deployment_environment {expected};" in block, names
        hosts.update(dict.fromkeys(names, expected))
    assert hosts
    return hosts


def request(port: int, hostname: str, path: str, expected: int, method="GET"):
    connection = http.client.HTTPSConnection(
        "127.0.0.1", port, timeout=3, context=ssl._create_unverified_context()
    )
    before = Upstream.calls
    try:
        connection.request(
            method,
            path,
            body=b"fixture" if method == "POST" else None,
            headers={"Host": hostname, "Connection": "Upgrade", "Upgrade": "websocket"},
        )
        response = connection.getresponse()
        response.read()
        assert response.status == expected, (hostname, path, response.status, expected)
        if expected == 503:
            assert response.getheader("X-Garment-Deployment-Gate") == "production/1"
            assert "no-store" in response.getheader("Cache-Control", "")
            assert response.getheader("Retry-After") == "60"
            assert Upstream.calls == before, "Blocked request reached the application"
    finally:
        connection.close()


def verify_config(nginx: str, openssl: str, config: Path, upstream: int) -> dict:
    source = config.read_text()
    hosts = managed_hosts(source)
    with tempfile.TemporaryDirectory(prefix="garment-public-gate-") as temporary:
        folder = Path(temporary)
        (folder / "empty").mkdir()
        (folder / "logs").mkdir()
        (folder / "maintenance").mkdir(mode=0o755)
        (folder / "production").mkdir()
        (folder / "maintenance.conf").write_text(
            (ROOT / "deploy/nginx/maintenance/server.conf")
            .read_text()
            .replace(
                "/srv/garment-buro/maintenance/", str(folder / "maintenance") + "/"
            )
        )
        (folder / "server-logging.conf").write_text(
            (privacy.LOGGING / "server.conf")
            .read_text()
            .replace("/var/log/nginx/access.log", str(folder / "access.log"))
        )
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
                "-keyout",
                str(folder / "key.pem"),
                "-out",
                str(folder / "cert.pem"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        (folder / "key.pem").chmod(0o600)
        http, https = privacy.free_port(), privacy.free_port()
        vhosts = privacy.render_vhosts(source, folder, upstream, http, https)
        (folder / "nginx.conf").write_text(
            f"daemon off; master_process off;\npid {folder}/nginx.pid; error_log {folder}/error.log;\n"
            f"events {{ worker_connections 128; }}\nhttp {{\nclient_body_temp_path {folder}/body; proxy_temp_path {folder}/proxy;\n"
            f"fastcgi_temp_path {folder}/fastcgi; uwsgi_temp_path {folder}/uwsgi;\n"
            f"scgi_temp_path {folder}/scgi;\n"
            f"include {privacy.LOGGING}/http.conf;\n" + vhosts + "\n}\n"
        )
        origins = folder / "production/public-origins.txt"
        addresses = f"https://localhost:{https}\nhttps://127.0.0.1:{https}\n"
        origins.write_text(addresses)
        environment = dict(
            os.environ,
            GARMENT_DEPLOY_ROOT=str(folder),
            SSL_CERT_FILE=str(folder / "cert.pem"),
        )

        def control(action, owner=OWNER, expected=0):
            arguments = [
                sys.executable,
                str(ROOT / "deploy/scripts/public-maintenance.py"),
                "production",
                action,
            ]
            if action != "check-open":
                arguments += ["--owner", owner]
            result = subprocess.run(
                arguments,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert result.returncode == expected, result.stderr

        def start():
            checked = subprocess.run(
                [nginx, "-t", "-p", str(folder), "-c", str(folder / "nginx.conf")],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            assert checked.returncode == 0, checked.stderr[-2000:]
            process = subprocess.Popen(
                [nginx, "-p", str(folder), "-c", str(folder / "nginx.conf")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(100):
                assert process.poll() is None, (
                    "Nginx rejected a repository configuration"
                )
                try:
                    with socket.create_connection(("127.0.0.1", https), timeout=0.1):
                        return process
                except OSError:
                    time.sleep(0.02)
            process.terminate()
            process.wait(timeout=5)
            raise AssertionError("Nginx did not become ready")

        def stop(process):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        process = start()
        try:
            control("check-open")
            control("close")
            paths = [
                ("/", "GET"),
                ("/api/orders", "POST"),
                ("/api/design-media", "POST"),
                ("/storage/garment-buro-production-media/fixture.png", "GET"),
                ("/_next/static/fixture.js", "GET"),
                ("/api/ws", "GET"),
            ]
            for hostname, env in hosts.items():
                for path, method in paths:
                    request(
                        https,
                        hostname,
                        path,
                        503 if env == "production" else 200,
                        method,
                    )
            control("open", owner=OTHER, expected=78)
            control("check-open", expected=78)
            # The marker is persistent; a proxy restart must not reopen traffic.
            stop(process)
            process = start()
            production_host = next(
                host for host, env in hosts.items() if env == "production"
            )
            request(https, production_host, "/api/orders", 503, "POST")
            # One origin reopens before another fails. The controller must reclose
            # without changing a committed application's images or database.
            origins.write_text(addresses + f"https://127.0.0.1:{privacy.free_port()}\n")
            control("open", expected=78)
            request(https, production_host, "/api/orders", 503, "POST")
            origins.write_text(addresses)
            control("open")
            assert not (folder / "maintenance/production.active").exists()
            for hostname in hosts:
                # The historical cutover example intentionally blocks order
                # creation even when maintenance is off. Preserve that policy.
                request(https, hostname, "/api/cart", 200, "POST")
            # A real 204 endpoint with a missing/shared-volume misconfiguration
            # is insufficient. Acquisition must observe the actual file switch.
            stop(process)
            snippet = folder / "maintenance.conf"
            snippet.write_text(
                snippet.read_text().replace(
                    str(folder / "maintenance") + "/",
                    str(folder / "unmounted-control") + "/",
                )
            )
            process = start()
            control("check-open")
            control("close", expected=78)
            assert not (folder / "maintenance/production.active").exists()
            request(https, production_host, "/api/cart", 200, "POST")
            return {
                "config": str(config.relative_to(ROOT)),
                "hosts": len(hosts),
                "paths": len(paths),
                "controllerTlsValidated": True,
                "restartRetainsGate": True,
                "blockedRequestsNeverReachUpstream": True,
                "partialReopeningReclosed": True,
                "unmountedMarkerRejected": True,
            }
        finally:
            stop(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nginx", default="nginx")
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        configs = [
            path for path in privacy.CONFIGS if "maintenance.conf" in path.read_text()
        ]
        assert len(configs) == 5, "Review the public Nginx topology inventory"
        reports = [
            verify_config(args.nginx, args.openssl, path, upstream.server_port)
            for path in configs
        ]
        print(json.dumps({"publicMaintenancePassed": True, "configurations": reports}))
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
