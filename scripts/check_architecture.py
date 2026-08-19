from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON_INWARD = [
    ROOT / "services/portfolio-ai/src/handsfree_portfolio/domain",
    ROOT / "services/portfolio-ai/src/handsfree_portfolio/application",
    ROOT / "services/portfolio-ai/src/handsfree_portfolio/ports",
]
PYTHON_FORBIDDEN = {
    "fastapi", "starlette", "neo4j", "graphiti_core", "boto3", "botocore",
    "openai", "anthropic", "redis", "uvicorn", "httpx",
}

WEB_APPLICATION = ROOT / "apps/web/src/application"
WEB_DESIGN_SYSTEM = ROOT / "apps/web/src/design-system"
WEB_FORBIDDEN_APPLICATION_PACKAGES = {"react", "react-dom", "neo4j", "openai", "@anthropic-ai/sdk"}
WEB_FORBIDDEN_APPLICATION_PATHS = ("../design-system", "../adapters", "../ui")
WEB_FORBIDDEN_DESIGN_PATHS = ("../application", "../adapters")


def python_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def extract_ts_imports(text: str) -> list[str]:
    imports: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if " from " in stripped and (stripped.startswith("import ") or stripped.startswith("export ")):
            quote = "'" if "'" in stripped else '"'
            parts = stripped.split(quote)
            if len(parts) >= 2:
                imports.append(parts[-2])
    return imports


def main() -> None:
    violations: list[str] = []
    for directory in PYTHON_INWARD:
        for path in directory.rglob("*.py"):
            forbidden = python_import_roots(path) & PYTHON_FORBIDDEN
            if forbidden:
                violations.append(f"{path.relative_to(ROOT)} imports forbidden inward dependency: {sorted(forbidden)}")

    for path in WEB_APPLICATION.rglob("*.ts*"):
        for imp in extract_ts_imports(path.read_text(encoding="utf-8")):
            package_root = "/".join(imp.split("/")[:2]) if imp.startswith("@") else imp.split("/")[0]
            if package_root in WEB_FORBIDDEN_APPLICATION_PACKAGES or imp.startswith(WEB_FORBIDDEN_APPLICATION_PATHS):
                violations.append(f"{path.relative_to(ROOT)} imports forbidden application dependency: {imp}")

    for path in WEB_DESIGN_SYSTEM.rglob("*.ts*"):
        for imp in extract_ts_imports(path.read_text(encoding="utf-8")):
            if imp.startswith(WEB_FORBIDDEN_DESIGN_PATHS):
                violations.append(f"{path.relative_to(ROOT)} theme/design code reaches behavior/adapter layer: {imp}")

    if violations:
        raise SystemExit("Architecture boundary violations:\n- " + "\n- ".join(violations))
    print("architecture-boundary: PASS")


if __name__ == "__main__":
    main()
