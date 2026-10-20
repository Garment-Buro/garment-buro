#!/usr/bin/env python3
"""Exercise repository vhosts and real Nginx access/error logs with synthetic secrets.

Only infrastructure addresses, TLS fixture paths and log paths are substituted.
No system installation, live configuration, real credentials or external requests.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = [
    ROOT / "nginx.conf",
    ROOT / "nginx.ssl.conf",
    ROOT / "nginx.bootstrap.conf",
    *sorted((ROOT / "deploy/nginx").glob("*.conf")),
    *sorted((ROOT / "deploy/nginx").glob("*.conf.example")),
]
LOGGING = ROOT / "deploy/nginx/logging"
MARKER = "SYNTHETIC_PRIVATE_" + "Q" * 43
FIELDS = {
    "timestamp",
    "request_id",
    "server",
    "method",
    "route",
    "status",
    "bytes",
    "duration_seconds",
    "upstream_status",
    "upstream_seconds",
}


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/disconnect" in self.path:
            self.connection.close()
            return
        self.send_response(401 if "/denied" in self.path else 200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args):
        pass


def free_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def render_vhosts(
    source: str, folder: Path, upstream: int, http: int, https: int
) -> str:
    count = len(re.findall(r"(?m)^server\s*\{", source))
    include = "include /etc/nginx/garment-buro/server-logging.conf;"
    if source.count(include) != count or not count:
        raise AssertionError(
            "Every vhost must explicitly override inherited access/error logs"
        )
    source = source.replace(include, f"include {folder}/server-logging.conf;")
    source = source.replace(
        "include /etc/nginx/garment-buro/maintenance.conf;",
        f"include {folder}/maintenance.conf;",
    )
    source = re.sub(r"listen \[::\]:\d+[^;]*;", "", source)
    source = re.sub(r"listen 80;", f"listen 127.0.0.1:{http};", source)
    source = re.sub(r"listen 443", f"listen 127.0.0.1:{https}", source)
    source = re.sub(
        r"ssl_certificate [^;]+;", f"ssl_certificate {folder}/cert.pem;", source
    )
    source = re.sub(
        r"ssl_certificate_key [^;]+;", f"ssl_certificate_key {folder}/key.pem;", source
    )
    source = re.sub(
        r"proxy_pass http://[^/;]+", f"proxy_pass http://127.0.0.1:{upstream}", source
    )
    source = re.sub(r"root [^;]+;", f"root {folder}/empty;", source)
    return source


def read_events(folder: Path) -> list[dict]:
    path = folder / "access.log"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def probe(
    folder: Path,
    port: int,
    hostname: str,
    path: str,
    *,
    tls: bool,
    expected: int,
    route: str,
    method: str = "GET",
    large_header: bool = False,
):
    before = len(read_events(folder))
    if tls:
        connection = http.client.HTTPSConnection(
            "127.0.0.1",
            port,
            timeout=3,
            context=ssl._create_unverified_context(),
        )
    else:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(
            method,
            path,
            headers={
                "Host": hostname,
                "Referer": f"https://example.invalid/{MARKER}",
                "User-Agent": MARKER,
                "Cookie": f"session={MARKER}",
                "Authorization": f"Bearer {MARKER}",
                "X-Request-ID": MARKER,
                "X-Fixture": MARKER * (1500 if large_header else 1),
            },
        )
        response = connection.getresponse()
        response.read()
        if response.status != expected:
            raise AssertionError(
                f"Unexpected fixture response: {response.status} != {expected}"
            )
    finally:
        connection.close()
    for _ in range(100):
        events = read_events(folder)
        if len(events) > before:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("A request was not recorded in the safe access log")
    event = events[-1]
    if set(event) != FIELDS or event["status"] != expected or event["route"] != route:
        raise AssertionError("Access event has unexpected fields, route or status")
    if event["method"] != ("OTHER" if method == MARKER else method):
        raise AssertionError("Request method was not normalized")
    if not re.fullmatch(r"[a-f0-9]{32}", event["request_id"]):
        raise AssertionError(
            "Edge request ID must be generated, never trusted from the client"
        )


def verify_config(
    nginx: str,
    openssl: str,
    config: Path,
    upstream: int,
    *,
    server_logging: str | None = None,
) -> int:
    with tempfile.TemporaryDirectory(prefix="garment-nginx-privacy-") as temporary:
        folder = Path(temporary)
        (folder / "empty").mkdir()
        (folder / "maintenance").mkdir()
        (folder / "maintenance.conf").write_text(
            (ROOT / "deploy/nginx/maintenance/server.conf")
            .read_text()
            .replace(
                "/srv/garment-buro/maintenance/", str(folder / "maintenance") + "/"
            )
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
                "/CN=fixture.invalid",
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
        http, https = free_port(), free_port()
        logging = (
            server_logging
            if server_logging is not None
            else (LOGGING / "server.conf").read_text()
        )
        (folder / "server-logging.conf").write_text(
            logging.replace("/var/log/nginx/access.log", str(folder / "access.log")),
        )
        vhosts = render_vhosts(config.read_text(), folder, upstream, http, https)
        (folder / "nginx.conf").write_text(
            "daemon off; master_process off;\n"
            f"pid {folder}/nginx.pid; error_log {folder}/main-error.log info;\n"
            "events { worker_connections 128; }\nhttp {\n"
            # Deliberately unsafe parent: each repository server must override it.
            f"access_log {folder}/inherited-combined.log combined;\n"
            f"client_body_temp_path {folder}/body; proxy_temp_path {folder}/proxy;\n"
            f"fastcgi_temp_path {folder}/fastcgi; uwsgi_temp_path {folder}/uwsgi;\n"
            f"scgi_temp_path {folder}/scgi;\n"
            f"include {LOGGING}/http.conf;\n" + vhosts + "\n}\n",
        )
        with (folder / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(
                [
                    nginx,
                    "-p",
                    str(folder),
                    "-c",
                    str(folder / "nginx.conf"),
                ],
                stdout=stderr,
                stderr=stderr,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise AssertionError(
                            "Nginx rejected a repository vhost configuration"
                        )
                    try:
                        with socket.create_connection(("127.0.0.1", http), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.02)
                else:
                    raise AssertionError("Fixture Nginx did not become ready")
                tls = "ssl_certificate " in vhosts
                port = https if tls else http
                hostname = re.search(r"server_name\s+([^;\s]+)", vhosts)[1]
                cases = (
                    [
                        (f"/api/design-media/{MARKER}/content", "design-media", 200),
                        (
                            f"/storage/garment-buro-production-crm-private/{MARKER}?X-Amz-Signature={MARKER}",
                            "storage",
                            200,
                        ),
                        (
                            f"/_next/image?url=%2Fapi%2Fdesign-media%2F{MARKER}&w=64&q=75",
                            "image-optimizer",
                            200,
                        ),
                        (f"/api/auth/denied?code={MARKER}", "auth", 401),
                        (f"/api/checkout/{MARKER}", "checkout", 200),
                        (f"/api/orders/{MARKER}", "orders", 200),
                        (f"/api/cart/{MARKER}", "cart", 200),
                        (f"/api/projects/{MARKER}", "customer", 200),
                        (f"/api/unknown/{MARKER}", "api", 200),
                        (f"/unknown/{MARKER}?email={MARKER}", "page", 200),
                        (f"/api/design-media/{MARKER}/disconnect", "design-media", 502),
                    ]
                    if tls
                    else [(f"/{MARKER}", "page", 200)]
                )
                # Bootstrap variants intentionally return 503 or proxy only to frontend.
                if config.name == "garment-buro.bootstrap.conf":
                    cases = [(f"/{MARKER}", "page", 503)]
                for path, route, status in cases:
                    try:
                        probe(
                            folder,
                            port,
                            hostname,
                            path,
                            tls=tls,
                            expected=status,
                            route=route,
                        )
                    except AssertionError as error:
                        raise AssertionError(
                            f"{config.name}, category {route}: {error}"
                        ) from error
                # Exercise every named vhost; never echo an unknown Host in logs.
                names = re.findall(r"server_name\s+([^;]+);", vhosts)
                for names_ in names:
                    host = names_.split()[0]
                    expected = (
                        503 if config.name == "garment-buro.bootstrap.conf" else 200
                    )
                    probe(
                        folder,
                        port,
                        host,
                        "/",
                        tls=tls,
                        expected=expected,
                        route="page",
                    )
                expected = 503 if config.name == "garment-buro.bootstrap.conf" else 501
                probe(
                    folder,
                    port,
                    MARKER.lower() + ".invalid",
                    "/",
                    tls=tls,
                    expected=expected,
                    route="page",
                    method=MARKER,
                )
                probe(
                    folder,
                    port,
                    hostname,
                    "/%ZZ" + MARKER,
                    tls=tls,
                    expected=400,
                    route="page",
                )
                probe(
                    folder,
                    port,
                    hostname,
                    "/" + MARKER,
                    tls=tls,
                    expected=400,
                    route="page",
                    large_header=True,
                )
                if tls:
                    probe(
                        folder,
                        http,
                        hostname,
                        f"/.well-known/acme-challenge/{MARKER}",
                        tls=False,
                        expected=404,
                        route="acme",
                    )
                    # HTTP redirect also carries private URLs; preserve redirect semantics.
                    probe(
                        folder,
                        http,
                        hostname,
                        f"/api/design-media/{MARKER}/content?q={MARKER}",
                        tls=False,
                        expected=301,
                        route="design-media",
                    )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for path in folder.glob("*.log"):
            content = path.read_text()
            if MARKER.lower() in content.lower():
                raise AssertionError(f"Synthetic private data leaked to {path.name}")
        inherited = folder / "inherited-combined.log"
        if inherited.exists() and inherited.stat().st_size:
            raise AssertionError("Vhost inherited the unsafe combined access log")
        return len(read_events(folder))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nginx", default="nginx")
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        requests = sum(
            verify_config(args.nginx, args.openssl, config, upstream.server_port)
            for config in CONFIGS
        )
        # Prove the gate detects both independent channels, rather than merely
        # accepting valid JSON or an empty log. Fixtures are never real secrets.
        safe = (LOGGING / "server.conf").read_text()
        for unsafe in (
            safe + "\naccess_log unsafe.log combined;\n",
            safe.replace("error_log /dev/null;", ""),
        ):
            try:
                verify_config(
                    args.nginx,
                    args.openssl,
                    CONFIGS[0],
                    upstream.server_port,
                    server_logging=unsafe,
                )
            except AssertionError as error:
                if "Synthetic private data leaked" not in str(error):
                    raise
            else:
                raise AssertionError(
                    "Privacy gate did not reject an unsafe logging configuration"
                )
        print(
            f"Nginx privacy: {len(CONFIGS)} configurations, {requests} safe access events; no private markers in logs"
        )
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
