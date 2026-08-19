from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts/schemas"
FIXTURE_PATH = ROOT / "contracts/fixtures/g0-contract-fixtures.json"


def main() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    schema_paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    missing = {path.name for path in schema_paths} - fixtures.keys()
    if missing:
        raise SystemExit(f"missing fixtures for schemas: {sorted(missing)}")

    for path in schema_paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(fixtures[path.name]), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(error.message for error in errors)
            raise SystemExit(f"{path.name}: fixture validation failed: {details}")
    print(f"contract-validation: PASS ({len(schema_paths)} schemas)")


if __name__ == "__main__":
    main()
