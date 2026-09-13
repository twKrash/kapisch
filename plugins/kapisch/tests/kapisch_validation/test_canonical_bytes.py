from __future__ import annotations

import unittest

from kapisch_validation.canonical_bytes import (
    canonical_json_bytes,
    canonical_json_line,
    canonical_text_bytes,
    normalize_utf8_text,
    sha256_hex,
)


class CanonicalBytesTests(unittest.TestCase):
    def test_public_text_json_and_exact_hash_contract(self) -> None:
        self.assertEqual(canonical_text_bytes("É\r\né\r\n\n"), "É\né\n".encode("utf-8"))
        self.assertEqual(normalize_utf8_text(b"a\r\nb\r"), b"a\nb\n")
        payload = {"é": "é", "z": [2, 1]}
        self.assertEqual(
            canonical_json_bytes(payload), '{"z":[2,1],"é":"é"}'.encode("utf-8")
        )
        self.assertEqual(canonical_json_line(payload), canonical_json_bytes(payload) + b"\n")
        self.assertEqual(
            sha256_hex(b"status: DONE\n"),
            "804aaae7bd1b6d3585d7f60cd58893771aa9439bbbfc76f62293ef7acb6898b4",
        )
        self.assertNotEqual(
            sha256_hex(b"status: DONE\n"), sha256_hex(b"status: DONE\r\n")
        )

    def test_unsupported_values_fail_before_bytes_exist(self) -> None:
        for value in (float("nan"), float("inf"), {"set"}, b"bytes", ("tuple",)):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                canonical_json_bytes(value)
        with self.assertRaises(ValueError):
            canonical_text_bytes("bad\udcff")
        with self.assertRaises(ValueError):
            canonical_text_bytes("\ufeffbom")

    def test_leading_bom_is_rejected_but_interior_scalar_is_preserved(self) -> None:
        with self.assertRaises(ValueError):
            canonical_text_bytes("\ufeffbom")
        expected = "a\ufeffb\n".encode("utf-8")
        self.assertEqual(canonical_text_bytes("a\ufeffb"), expected)
        self.assertEqual(normalize_utf8_text("a\ufeffb".encode("utf-8")), expected)
