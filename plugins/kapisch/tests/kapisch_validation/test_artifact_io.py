from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kapisch_validation.artifact_io import (
    ArtifactFailureKind,
    load_toml_artifact,
    read_utf8_artifact,
)


class ArtifactIoTests(unittest.TestCase):
    def test_read_utf8_classifies_expected_input_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing.toml"
            artifact, failure = read_utf8_artifact(missing)
            self.assertIsNone(artifact)
            self.assertEqual(failure.kind, ArtifactFailureKind.MISSING)

            invalid = root / "invalid.toml"
            invalid.write_bytes(b"\xff")
            artifact, failure = read_utf8_artifact(invalid)
            self.assertIsNone(artifact)
            self.assertEqual(failure.kind, ArtifactFailureKind.INVALID_UTF8)

            readable = root / "readable.toml"
            readable.write_text('key = "value"\n', encoding="utf-8")
            artifact, failure = read_utf8_artifact(readable)
            self.assertIsNone(failure)
            self.assertEqual(artifact.text, 'key = "value"\n')

    def test_read_utf8_classifies_os_errors_without_catching_unexpected_ones(self) -> None:
        path = Path("artifact.toml")
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("denied")):
            artifact, failure = read_utf8_artifact(path)
        self.assertIsNone(artifact)
        self.assertEqual(failure.kind, ArtifactFailureKind.UNREADABLE)

        with mock.patch.object(Path, "read_bytes", side_effect=RuntimeError("bug")):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                read_utf8_artifact(path)

    def test_load_toml_classifies_malformed_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact.toml"
            path.write_text("value = [", encoding="utf-8")
            raw, failure = load_toml_artifact(path)
        self.assertIsNone(raw)
        self.assertEqual(failure.kind, ArtifactFailureKind.MALFORMED_TOML)


if __name__ == "__main__":
    unittest.main()
