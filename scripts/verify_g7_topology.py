from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "deploy" / "compose.production.yml"
CADDY_PATH = ROOT / "deploy" / "Caddyfile"
API_DOCKERFILE = ROOT / "deploy" / "api.Dockerfile"
CADDY_DOCKERFILE = ROOT / "deploy" / "caddy.Dockerfile"
WEB_ROOT = ROOT / "apps" / "web"
PYPROJECT = ROOT / "services" / "portfolio-ai" / "pyproject.toml"

FORBIDDEN_RUNTIME_ENV_FRAGMENTS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "PRIVATE",
    "AWS_",
    "S3_",
    "R2_",
    "NEO4J",
    "GRAPHITI",
)
ALLOWED_WEB_ENV = {"VITE_PORTFOLIO_API_URL"}


def _fail(message: str) -> None:
    raise SystemExit(message)


def _environment_keys(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, dict):
        return {str(key) for key in value}
    if isinstance(value, list):
        return {str(item).split("=", 1)[0] for item in value}
    _fail("compose environment must be a mapping or list")
    return set()


def _published_ports(service: dict[str, Any]) -> set[str]:
    ports = service.get("ports") or []
    return {str(item) for item in ports}


def _assert_pack_mount(api: dict[str, Any]) -> None:
    mounts = api.get("volumes") or []
    matching = [
        item
        for item in mounts
        if isinstance(item, dict)
        and item.get("target") == "/var/lib/handsfree/portfolio-public"
    ]
    if len(matching) != 1:
        _fail("api must have exactly one FOSSIL pack mount")
    mount = matching[0]
    if mount.get("type") != "bind" or mount.get("read_only") is not True:
        _fail("FOSSIL public pack must be a read-only bind mount")


def _scan_web_env() -> set[str]:
    found: set[str] = set()
    pattern = re.compile(r"import\.meta\.env\.([A-Z0-9_]+)")
    for path in WEB_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    return found


def _assert_digest_pinned_images(path: Path) -> list[str]:
    images: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.upper().startswith("FROM "):
            continue
        image = line.split()[1]
        images.append(image)
        if "@sha256:" not in image:
            _fail(f"production base image is not digest pinned in {path.name}: {image}")
    if not images:
        _fail(f"no base images found in {path.name}")
    return images


def verify() -> dict[str, Any]:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = compose.get("services") or {}
    if set(services) != {"caddy", "api"}:
        _fail("minimal production compose must contain only caddy and api services")

    caddy = services["caddy"]
    api = services["api"]
    if _published_ports(caddy) != {"80:80", "443:443"}:
        _fail("Caddy must be the only public service and publish exactly 80/443")
    if api.get("ports"):
        _fail("api must not publish a host port")
    if {str(value) for value in (api.get("expose") or [])} != {"8000"}:
        _fail("api must expose only its internal 8000 port")

    backend = (compose.get("networks") or {}).get("backend") or {}
    if backend.get("internal") is not True:
        _fail("backend network must be internal")
    if set(api.get("networks") or []) != {"backend"}:
        _fail("api must attach only to the internal backend network")
    if set(caddy.get("networks") or []) != {"edge", "backend"}:
        _fail("Caddy must bridge edge and backend networks")

    if api.get("read_only") is not True:
        _fail("api root filesystem must be read-only")
    if "ALL" not in {str(value) for value in (api.get("cap_drop") or [])}:
        _fail("api must drop all Linux capabilities")
    if "no-new-privileges:true" not in {str(value) for value in (api.get("security_opt") or [])}:
        _fail("api must enable no-new-privileges")
    _assert_pack_mount(api)

    runtime_env = _environment_keys(api.get("environment"))
    forbidden_runtime_env = sorted(
        key
        for key in runtime_env
        if any(fragment in key.upper() for fragment in FORBIDDEN_RUNTIME_ENV_FRAGMENTS)
    )
    if forbidden_runtime_env:
        _fail(f"public api runtime contains forbidden credential/config names: {forbidden_runtime_env}")

    caddyfile = CADDY_PATH.read_text(encoding="utf-8")
    if "@api path /health /v1/*" not in caddyfile:
        _fail("Caddy must define the bounded health/API matcher")
    if "handle @api" not in caddyfile or "reverse_proxy api:8000" not in caddyfile:
        _fail("Caddy must route API requests through a dedicated handle before static fallback")
    if "handle {" not in caddyfile or "try_files {path} /index.html" not in caddyfile:
        _fail("Caddy must keep SPA fallback inside the non-API handle")
    for forbidden in (":7687", ":7474", "neo4j", "graphiti"):
        if forbidden.lower() in caddyfile.lower():
            _fail(f"Caddy public configuration references forbidden projection surface: {forbidden}")

    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    default_dependencies = [str(value).lower() for value in pyproject["project"]["dependencies"]]
    if any("neo4j" in value or "graphiti" in value for value in default_dependencies):
        _fail("Neo4j/Graphiti must not be a default production dependency")
    projection_dependencies = [
        str(value).lower()
        for value in pyproject["project"]["optional-dependencies"].get("projection", [])
    ]
    if not any("neo4j" in value for value in projection_dependencies):
        _fail("historical Neo4j projection adapter must remain explicitly optional")

    api_dockerfile = API_DOCKERFILE.read_text(encoding="utf-8").lower()
    if "pip install /src/services/portfolio-ai" not in api_dockerfile:
        _fail("api image must install the default application dependency set")
    if "[projection]" in api_dockerfile or "neo4j" in api_dockerfile or "graphiti" in api_dockerfile:
        _fail("api image must not install projection dependencies")

    base_images = _assert_digest_pinned_images(API_DOCKERFILE) + _assert_digest_pinned_images(CADDY_DOCKERFILE)

    web_env = _scan_web_env()
    unexpected_web_env = sorted(web_env - ALLOWED_WEB_ENV)
    if unexpected_web_env:
        _fail(f"frontend references unexpected build/runtime environment names: {unexpected_web_env}")

    result = {
        "status": "PASS",
        "publicServices": ["caddy"],
        "publicPorts": [80, 443],
        "apiPublishedPorts": [],
        "backendInternal": True,
        "apiReadOnlyRoot": True,
        "apiDropsAllCapabilities": True,
        "packMountReadOnly": True,
        "runtimeCredentialNames": [],
        "defaultProjectionDependencies": [],
        "frontendEnvironmentNames": sorted(web_env),
        "graphServiceDeployed": False,
        "apiRoutingIsolatedFromSpaFallback": True,
        "baseImagesDigestPinned": True,
        "baseImages": base_images,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = verify()
    encoded = json.dumps(result, sort_keys=True)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
