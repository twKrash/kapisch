from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))
from kapisch_core.bundle import compile_bundle


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or check the canonical CoreBundle")
    parser.add_argument("--check", action="store_true", help="fail if generated bundle copies are stale")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()
    expected = compile_bundle(root / "core")
    outputs = (
        root / "core/dist/core-bundle.json",
        root / "core/kapisch_core/resources/core-bundle.json",
        root / "tests/conformance/fixtures/v3/bundle.json",
    )
    if args.check:
        stale = [str(path.relative_to(root)) for path in outputs if not path.is_file() or path.read_bytes() != expected]
        if stale:
            print("stale or missing CoreBundle: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("CoreBundle copies match canonical sources")
        return 0
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
    print(f"built {len(outputs)} identical CoreBundle copies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
