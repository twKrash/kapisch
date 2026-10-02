from __future__ import annotations

import json
import unittest
from io import StringIO
from unittest.mock import patch

from kapisch_core.cli import main
from kapisch_core.validation import ValidationError


class CliTests(unittest.TestCase):
    def test_invalid_run_returns_json_error_and_failure(self) -> None:
        output = StringIO()
        with patch("kapisch_core.cli.validate_run", return_value=[
                ValidationError("state-unavailable", "missing", None)]), patch("sys.stdout", output):
            self.assertEqual(main(["--repo", ".", "--run", "missing", "--json"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {
            "protocol_version": 3, "ok": False,
            "errors": [{"code": "state-unavailable", "message": "missing", "path": None}],
        })

    def test_validation_exception_returns_failure(self) -> None:
        output = StringIO()
        with patch("kapisch_core.cli.validate_run", side_effect=OSError("denied")), patch("sys.stdout", output):
            self.assertEqual(main(["--repo", ".", "--run", "run"]), 1)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "validation-failed")


if __name__ == "__main__":
    unittest.main()
