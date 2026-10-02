from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validation import validate_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kapisch-validate")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--gate")
    args = parser.parse_args(argv)

    try:
        errors = validate_run(args.repo, args.run, args.gate)
        result = {"protocol_version": 3, "ok": not errors,
                  "errors": [{"code": error.code, "message": error.message, "path": error.path}
                             for error in errors]}
    except (OSError, ValueError) as error:
        result = {"protocol_version": 3, "ok": False,
                  "errors": [{"code": "validation-failed", "message": str(error), "path": None}]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
