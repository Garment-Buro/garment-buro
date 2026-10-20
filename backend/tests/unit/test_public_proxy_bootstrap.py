import runpy
from pathlib import Path

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[3] / "deploy/scripts/install-public-release-gate.py")
)
patch_nginx = MODULE["patch_nginx"]
patch_override = MODULE["patch_override"]

OTHER = """server {
    listen 443 ssl;
    server_name tverfactory.ru;
    location / { return 200 "unchanged { content }"; }
}
server { listen 443 ssl; server_name widget.garment-buro.ru; return 200 "widget"; }
"""
SOURCE = (
    """# A comment containing braces: { }
server { listen 80; server_name garment-buro.ru widget.garment-buro.ru; return 301 https://$host$request_uri; }
server { listen 443 ssl; server_name garment-buro.ru www.garment-buro.ru; location / { proxy_pass http://172.17.0.1:3200; } }
server { listen 443 ssl; server_name partner.garment-buro.ru; location / { proxy_pass http://172.17.0.1:3200; } }
server { listen 443 ssl; server_name production.garment-buro.ru; location / { proxy_pass http://172.17.0.1:3200; } }
server { listen 443 ssl; server_name dev.garment-buro.ru; location / { proxy_pass http://172.17.0.1:3100; } }
"""
    + OTHER
)


def test_patch_preserves_unrelated_sites_routes_and_quoted_braces():
    result = patch_nginx(SOURCE)
    assert OTHER in result
    assert result.count("include /etc/nginx/garment-buro/maintenance.conf;") == 4
    assert result.count("include /etc/nginx/garment-buro/server-logging.conf;") == 5
    assert result.count("set $garment_deployment_environment production;") == 3
    assert result.count("proxy_pass http://172.17.0.1:3200;") == 3
    assert "proxy_pass http://172.17.0.1:3100;" in result


@pytest.mark.parametrize(
    "source",
    [
        SOURCE.replace("production.garment-buro.ru", "unknown.example"),
        SOURCE.replace(
            "server_name partner.garment-buro.ru",
            "server_name partner.garment-buro.ru unrelated.example",
        ),
        SOURCE + "{",
        SOURCE + "\n# /etc/nginx/garment-buro/maintenance.conf already configured",
    ],
)
def test_unsafe_or_incomplete_proxy_fails_before_installation(source):
    with pytest.raises(ValueError):
        patch_nginx(source)


def test_override_preserves_existing_hosts_and_unrelated_services():
    source = "services:\n  nginx:\n    extra_hosts:\n      - host.docker.internal:host-gateway\n  other:\n    image: unchanged\n"
    result = patch_override(source)
    assert result.endswith("  other:\n    image: unchanged\n")
    assert "    extra_hosts:\n      - host.docker.internal:host-gateway\n" in result
    assert result.count(":ro\n") == 4
    assert "/srv/garment-buro/maintenance:/srv/garment-buro/maintenance:ro" in result


def test_existing_override_mounts_require_review_instead_of_replacement():
    with pytest.raises(ValueError):
        patch_override("services:\n  nginx:\n    volumes:\n      - ./existing:/existing:ro\n")
