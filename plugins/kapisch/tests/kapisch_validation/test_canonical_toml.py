from __future__ import annotations
import tomllib, unittest
from kapisch_validation.canonical_toml import render_toml, toml_basic_string
class CanonicalTomlTests(unittest.TestCase):
 def test_dotted_extension_keys_round_trip_as_literal_keys(self):
  data={'extensions':{'com.example':{'value':'x'}},'com.example':'root'}
  self.assertEqual(tomllib.loads(render_toml(data).decode()),data)
 def test_forbidden_controls_round_trip(self):
  data={"nul":"\0","del":"\x7f","tab":"\t","newline":"\n"}
  self.assertEqual(tomllib.loads(render_toml(data).decode()),data)
 def test_public_golden_and_surrogate_rejection(self):
  data={"extensions":{"z.example":{"b":2,"a":1}},"ordered":["b","a"],"text":"é\n\x7f","version":1}
  self.assertEqual(render_toml(data,key_order=("version","text","ordered","extensions")),('"version" = 1\n'+'"text" = "é\\n\\u007f"\n'+'"ordered" = ["b", "a"]\n'+'"extensions" = {"z.example" = {"a" = 1, "b" = 2}}\n').encode("utf-8"))
  with self.assertRaisesRegex(ValueError,"unpaired Unicode surrogate"):
   toml_basic_string("bad\udcff")
