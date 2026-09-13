from pathlib import Path
import tempfile
import unittest

from kapisch_validation.path_atoms import (
    canonical_relative_path,
    is_portable_filename_atom,
    validate_relative_posix_path,
)


class PortablePathTests(unittest.TestCase):
    def test_contained_native_path_becomes_relative_posix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = (Path(temporary) / "répo with spaces").absolute()
            path = root / "Reviews With Space" / "RÉSUMÉ" / "CON. "
            self.assertEqual(canonical_relative_path(path, root=root), "Reviews With Space/RÉSUMÉ/CON. ")

    def test_path_components_are_less_strict_than_filename_atoms(self) -> None:
        valid = ("CON", "dir.", "name ", "segment:label", "é:tiquette", "Ω:label", "a/\x01/\x7f", "a/<b>", 'a/quo"te', "a/star*", "a/question?", "a/pipe|")
        for value in valid:
            with self.subTest(value=value):
                self.assertEqual(validate_relative_posix_path(value), value)
        for value in ("CON", "dir.", "name ", "segment:label", "a/<b>", 'a/quo"te', "a/star*", "a/question?", "a/pipe|"):
            atom = value.rsplit("/", 1)[-1]
            with self.subTest(atom=atom):
                self.assertFalse(is_portable_filename_atom(atom))

    def test_invalid_or_escaping_paths_fail(self) -> None:
        invalid = (None, 42, "", ".", "..", "a/../b", "a//b", "/abs", "C:/abs", "C:relative", r"\\server\share", "a\\b", "a/", "a\0b")
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_relative_posix_path(value)
        with tempfile.TemporaryDirectory() as temporary:
            root = (Path(temporary) / "root").absolute()
            with self.assertRaises(ValueError):
                canonical_relative_path(root.parent / "outside", root=root)
            with self.assertRaises(ValueError):
                canonical_relative_path(root, root=root)
            with self.assertRaises(ValueError):
                canonical_relative_path(Path("relative/file"), root=root)
            with self.assertRaises(ValueError):
                canonical_relative_path(Path("file"), root=root)
            with self.assertRaises(ValueError):
                canonical_relative_path(root, root=Path("relative-root"))
            with self.assertRaises(ValueError):
                canonical_relative_path("not-a-path", root=root)
            with self.assertRaises(ValueError):
                canonical_relative_path(root / "file", root="not-a-root")
