from __future__ import annotations

import ast
import posixpath
import re
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
CORE_HOST = re.compile(
    r"\b(?:codex|pi)\b|\.codex\b|\.pi\b|openai|sandbox_mode|marketplace|\.toml",
    re.IGNORECASE,
)
HOST_IMPORT = re.compile(
    r"\b(?:from|import)\s+(?:harnesses\.(?:codex|pi)|plugins\.kapisch)"
)
HOST_PATH = re.compile(
    r"(?:harnesses[/\\](?:codex|pi)|plugins[/\\]kapisch[/\\])", re.IGNORECASE
)


def _source_files(root: Path, relative: str) -> dict[str, str]:
    base = root / relative
    if not base.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in base.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".toml"}
    }


def _core_imports_allowed(path: str, source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    package_parts = PurePosixPath(path).parent.parts
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = (alias.name for alias in node.names)
            if any(
                module.split(".")[0]
                not in sys.stdlib_module_names | {"kapisch_core", "__future__"}
                for module in modules
            ):
                return False
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                climb = node.level - 1
                if climb > len(package_parts):
                    return False
                base = package_parts[: len(package_parts) - climb]
                modules = (
                    [node.module]
                    if node.module
                    else [alias.name.split(".")[0] for alias in node.names]
                )
                targets = ("/".join((*base, *module.split("."))) for module in modules)
                if any(
                    target != "core/kapisch_core"
                    and not target.startswith("core/kapisch_core/")
                    for target in targets
                ):
                    return False
            elif (node.module or "").split(".")[0] not in sys.stdlib_module_names | {
                "kapisch_core",
                "__future__",
            }:
                return False
    return True


def _under_adapter(path: str, adapter: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        len(parts) >= 2
        and parts[0].lower() == "harnesses"
        and parts[1].lower() == adapter
    )


def _has_relative_cross_adapter_reference(
    path: str, source: str, target_adapter: str
) -> bool:
    source_path = PurePosixPath(path.replace("\\", "/"))
    for match in re.finditer(r"['\"]((?:\.{1,2}[/\\\\])+[^'\"]+)['\"]", source):
        reference = match.group(1).replace("\\", "/")
        resolved = posixpath.normpath(str(source_path.parent / reference))
        if _under_adapter(resolved, target_adapter):
            return True

    if source_path.suffix.lower() == ".py":
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        if tree is not None:
            package_parts = source_path.parent.parts
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level == 0:
                    continue
                climb = node.level - 1
                if climb > len(package_parts):
                    continue
                base = package_parts[: len(package_parts) - climb]
                modules = (
                    [node.module]
                    if node.module
                    else [alias.name.split(".")[0] for alias in node.names]
                )
                if any(
                    _under_adapter(
                        "/".join((*base, *module.split("."))), target_adapter
                    )
                    for module in modules
                ):
                    return True
    return False


def boundary_violations(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for path, source in files.items():
        normalized = path.lower()
        if normalized.startswith("core/"):
            if (
                CORE_HOST.search(source)
                or HOST_IMPORT.search(source)
                or HOST_PATH.search(source)
            ):
                violations.append(f"core host dependency: {path}")
            elif path.lower().endswith(".py") and not _core_imports_allowed(
                path, source
            ):
                violations.append(f"core import outside stdlib/core: {path}")
        elif normalized.startswith("harnesses/codex/"):
            if (
                re.search(r"\bharnesses\.pi\b", source)
                or re.search(r"harnesses[/\\]pi[/\\]", source, re.IGNORECASE)
                or _has_relative_cross_adapter_reference(path, source, "pi")
            ):
                violations.append(f"Codex adapter reads/imports Pi: {path}")
        elif normalized.startswith("harnesses/pi/"):
            if (
                re.search(r"\bharnesses\.codex\b", source)
                or re.search(r"harnesses[/\\]codex[/\\]", source, re.IGNORECASE)
                or _has_relative_cross_adapter_reference(path, source, "codex")
            ):
                violations.append(f"Pi adapter reads/imports Codex: {path}")
    return violations


class BoundaryTests(unittest.TestCase):
    def test_core_imports_are_limited_to_stdlib_and_core(self) -> None:
        files = {
            "core/kapisch_core/allowed.py": "import sys\nfrom .domain import Role\n",
            "core/kapisch_core/tooling.py": "import tooling\n",
            "core/kapisch_core/third_party.py": "import requests\n",
        }
        self.assertEqual(
            boundary_violations(files),
            [
                "core import outside stdlib/core: core/kapisch_core/tooling.py",
                "core import outside stdlib/core: core/kapisch_core/third_party.py",
            ],
        )

    def test_fake_conformance_sources_have_no_host_dependencies(self) -> None:
        for relative in (
            "tooling/conformance/adapter.py",
            "tests/conformance/fake_adapter.py",
            "tests/conformance/test_fake_adapter.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIsNone(CORE_HOST.search(source), relative)
            self.assertIsNone(HOST_IMPORT.search(source), relative)
            self.assertIsNone(HOST_PATH.search(source), relative)

    def test_core_sources_have_no_host_imports_tokens_or_paths(self) -> None:
        files = _source_files(ROOT, "core")
        self.assertTrue(files, "Stage 1 must create the host-neutral core package")
        self.assertEqual(boundary_violations(files), [])

    def test_boundary_checker_resolves_relative_imports_and_reads(self) -> None:
        files = {
            "harnesses/codex/src/adapter.py": "from ...pi import policy\n",
            "harnesses/pi/src/adapter.ts": 'readFileSync("../../codex/dist/agent.md")\n',
        }
        violations = boundary_violations(files)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("Codex" in item and "Pi" in item for item in violations))
        self.assertTrue(any("Pi" in item and "Codex" in item for item in violations))

    def test_boundary_checker_rejects_cross_adapter_imports_and_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "harnesses/codex/src").mkdir(parents=True)
            (root / "harnesses/pi/src").mkdir(parents=True)
            (root / "harnesses/codex/src/adapter.py").write_text(
                "from harnesses.pi import policy\n"
            )
            (root / "harnesses/pi/src/adapter.ts").write_text(
                'readFileSync("harnesses/codex/dist/agent.md")\n'
            )
            files = {
                path.relative_to(root).as_posix(): path.read_text()
                for path in root.rglob("*")
                if path.is_file()
            }
        violations = boundary_violations(files)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("Codex" in item and "Pi" in item for item in violations))
        self.assertTrue(any("Pi" in item and "Codex" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
