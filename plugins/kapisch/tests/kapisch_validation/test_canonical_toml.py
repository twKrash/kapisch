from __future__ import annotations
import tomllib, unittest
from kapisch_validation.canonical_toml import render_toml
class CanonicalTomlTests(unittest.TestCase):
 def test_dotted_extension_keys_round_trip_as_literal_keys(self):
  data={'extensions':{'com.example':{'value':'x'}},'com.example':'root'}
  self.assertEqual(tomllib.loads(render_toml(data).decode()),data)
