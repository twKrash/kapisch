from __future__ import annotations
import subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class ToolTests(unittest.TestCase):
 def test_help(self):
  for name in ('render_controller_view.py','migrate_controller_view_v4.py'):
   self.assertEqual(subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--help']).returncode,0)
