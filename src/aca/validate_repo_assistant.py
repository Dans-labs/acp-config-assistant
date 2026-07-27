from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from src.aca.models.repository_assistant_config import RepoAssistantDataModel


def _iter_json_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        else:
            files.append(path)
    return files


def _format_loc(loc: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in loc)


def validate_file(path: Path) -> bool:
    if not path.exists():
        print(f"❌ {path}: file does not exist")
        return False

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ {path}: invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})")
        return False

    try:
        RepoAssistantDataModel.model_validate(payload)
        print(f"✅ {path}: valid")
        return True
    except ValidationError as exc:
        print(f"❌ {path}: invalid")
        for err in exc.errors():
            loc = _format_loc(err.get("loc", ()))
            msg = err.get("msg", "validation error")
            err_type = err.get("type", "unknown")
            print(f"  - {loc}: {msg} ({err_type})")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ACA repository assistant JSON config(s) against RepoAssistantDataModel.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="JSON file path(s) or directory path(s) containing .json files.",
    )
    args = parser.parse_args()

    files = _iter_json_files(args.paths)
    if not files:
        print("No JSON files found.")
        return 1

    all_valid = True
    for path in files:
        all_valid = validate_file(path) and all_valid

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
