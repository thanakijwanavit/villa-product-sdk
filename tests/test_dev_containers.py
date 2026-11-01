"""vps-4wr: the dev containers expose nothing beyond this machine, and Jupyter never runs without a token."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = (ROOT / "docker-compose.yml").read_text()


def published_ports():
    # every "- [ip:]host:container" list item (a volume such as ".:/data/" does not match)
    return re.findall(r'^\s*-\s*"?((?:[\d.]+:)?\d+:\d+)"?\s*(?:#.*)?$', COMPOSE, flags=re.M)


def test_ports_bind_to_loopback_only():
    assert sorted(published_ports()) == ["127.0.0.1:4000:4000", "127.0.0.1:8080:8080"]


def test_jupyter_needs_a_token_from_the_environment():
    assert "token=''" not in COMPOSE and "password=''" not in COMPOSE
    assert re.search(r"JUPYTER_TOKEN:\s*\$\{JUPYTER_TOKEN:\?", COMPOSE), "compose must refuse to start without JUPYTER_TOKEN"
    assert "JUPYTER_TOKEN" in (ROOT / "CONTRIBUTING.md").read_text()


def test_devcontainer_mounts_no_docker_socket_and_publishes_no_port():
    text = (ROOT / ".devcontainer.json").read_text()
    config = json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))  # JSONC: drop the comment lines
    assert "docker.sock" not in json.dumps(config)
    assert "appPort" not in config
