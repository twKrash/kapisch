from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from kapisch_validation.artifact_io import (
    ArtifactFailureKind,
    contained_artifact_path,
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
            readable.write_bytes(b'key = "value"\n')
            artifact, failure = read_utf8_artifact(readable)
            self.assertIsNone(failure)
            self.assertEqual(artifact.data, b'key = "value"\n')
            self.assertEqual(artifact.text, 'key = "value"\n')

    def test_read_utf8_classifies_os_errors_without_catching_unexpected_ones(self) -> None:
        path = Path("artifact.toml")
        with mock.patch(
            "kapisch_validation.artifact_io.os.open", side_effect=PermissionError("denied")
        ):
            artifact, failure = read_utf8_artifact(path)
        self.assertIsNone(artifact)
        self.assertEqual(failure.kind, ArtifactFailureKind.UNREADABLE)

        with (
            mock.patch("kapisch_validation.artifact_io.os.open", return_value=3),
            mock.patch(
                "kapisch_validation.artifact_io.os.fstat",
                return_value=SimpleNamespace(st_mode=0o100000),
            ),
            mock.patch(
                "kapisch_validation.artifact_io.os.read", side_effect=RuntimeError("bug")
            ),
            mock.patch("kapisch_validation.artifact_io.os.close"),
        ):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                read_utf8_artifact(path)

    def test_read_utf8_rejects_non_regular_files_before_reading(self) -> None:
        with (
            mock.patch("kapisch_validation.artifact_io.os.open", return_value=3),
            mock.patch(
                "kapisch_validation.artifact_io.os.fstat",
                return_value=SimpleNamespace(st_mode=0o010000),
            ),
            mock.patch("kapisch_validation.artifact_io.os.read") as read,
            mock.patch("kapisch_validation.artifact_io.os.close") as close,
        ):
            artifact, failure = read_utf8_artifact(Path("artifact.toml"))
        self.assertIsNone(artifact)
        self.assertEqual(failure.kind, ArtifactFailureKind.NOT_REGULAR)
        read.assert_not_called()
        close.assert_called_once_with(3)

    def test_read_utf8_requests_binary_mode_when_available(self) -> None:
        with (
            mock.patch("kapisch_validation.artifact_io.os.O_BINARY", 0x8000, create=True),
            mock.patch("kapisch_validation.artifact_io.os.open", return_value=3) as open,
            mock.patch(
                "kapisch_validation.artifact_io.os.fstat",
                return_value=SimpleNamespace(st_mode=0o100000),
            ),
            mock.patch(
                "kapisch_validation.artifact_io.os.read", side_effect=(b"a\r\nb\r\n", b"")
            ),
            mock.patch("kapisch_validation.artifact_io.os.close"),
        ):
            artifact, failure = read_utf8_artifact(Path("artifact.toml"))
        self.assertIsNone(failure)
        self.assertEqual(artifact.data, b"a\r\nb\r\n")
        self.assertEqual(open.call_args.args[1] & 0x8000, 0x8000)

    def test_contained_path_uses_canonical_binary_reader_for_exact_bytes(self) -> None:
        """This runs natively on Windows too, where exact bytes must survive."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence.txt"
            expected = b"first\r\n\x1asecond\r\n"
            evidence.write_bytes(expected)

            path = contained_artifact_path(root, "evidence.txt")
            self.assertEqual(path, evidence.resolve())
            artifact, failure = read_utf8_artifact(path)

        self.assertIsNone(failure)
        self.assertEqual(artifact.data, expected)
        self.assertEqual(artifact.text, expected.decode("utf-8"))

    def test_contained_path_rejects_escapes_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "evidence.txt").write_text("evidence\n", encoding="utf-8")
            self.assertIsNone(contained_artifact_path(root, "../evidence.txt"))
            self.assertIsNone(contained_artifact_path(root, "\0"))
            if hasattr(Path, "symlink_to"):
                link = root / "evidence-link.txt"
                try:
                    link.symlink_to("evidence.txt")
                except OSError:
                    self.skipTest("symlink creation is unavailable")
                self.assertIsNone(contained_artifact_path(root, link.name))

    def test_load_toml_classifies_parser_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact.toml"
            for content, detail in (
                ("value = [", None),
                ("value = " + "9" * 5_000, "TOML input is malformed"),
                ("value = " + "[" * 1_500 + "]" * 1_500, "TOML input is malformed"),
            ):
                with self.subTest(content_prefix=content[:10]):
                    path.write_text(content, encoding="utf-8")
                    raw, failure = load_toml_artifact(path)
                    self.assertIsNone(raw)
                    self.assertEqual(failure.kind, ArtifactFailureKind.MALFORMED_TOML)
                    if detail is not None:
                        self.assertEqual(failure.detail, detail)


if __name__ == "__main__":
    unittest.main()
