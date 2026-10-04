import importlib.util
import unittest


class ProtocolFormatsTests(unittest.TestCase):
    def test_private_protocol_formats(self):
        self.assertIsNotNone(importlib.util.find_spec("kapisch_core._protocol_formats"))
        from kapisch_core._protocol_formats import (
            is_rfc3339_timestamp,
            is_sha256_digest,
        )

        self.assertTrue(is_rfc3339_timestamp("2024-01-02T03:04:05Z"))
        self.assertTrue(is_rfc3339_timestamp("2024-01-02T03:04:05+05:30"))
        self.assertTrue(is_rfc3339_timestamp("2016-12-31T23:59:60Z"))
        self.assertTrue(is_rfc3339_timestamp("2017-01-01T00:59:60+01:00"))
        self.assertFalse(is_rfc3339_timestamp("2016-12-30T23:59:60Z"))
        self.assertFalse(is_rfc3339_timestamp("2024-01-02T03:04:05+24:00"))
        self.assertFalse(is_rfc3339_timestamp("2024-01-02T03:04:05+00:60"))
        self.assertTrue(is_sha256_digest("a" * 64))
        self.assertFalse(is_sha256_digest("g" * 64))
        self.assertFalse(is_sha256_digest("A" * 64))


if __name__ == "__main__":
    unittest.main()
