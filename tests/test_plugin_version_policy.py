from __future__ import annotations
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CHECKER=ROOT/'scripts/check_plugin_version.py'
class VersionPolicyTests(unittest.TestCase):
 def run_case(self, changed='plugins/kapisch/kapisch_validation/x.py', base='1.1.0', candidate='1.1.0', changelog=True, mismatch=False):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory); (root/'scripts').mkdir();shutil.copy(CHECKER,root/'scripts/check_plugin_version.py')
   for version in (base,): self.files(root,version,version,True)
   subprocess.run(['git','init','-q'],cwd=root,check=True);subprocess.run(['git','config','user.email','test@example.com'],cwd=root,check=True);subprocess.run(['git','config','user.name','Test'],cwd=root,check=True);subprocess.run(['git','add','.'],cwd=root,check=True);subprocess.run(['git','commit','-qm','base'],cwd=root,check=True)
   self.files(root,candidate,'9.9.9' if mismatch else candidate,changelog);target=root/changed;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('changed');subprocess.run(['git','add','.'],cwd=root,check=True);subprocess.run(['git','commit','-qm','candidate'],cwd=root,check=True)
   result=subprocess.run([sys.executable,'scripts/check_plugin_version.py','--base','HEAD~1'],cwd=root,text=True,capture_output=True)
  return result
 def files(self,root,json_version,py_version,changelog):
  metadata=root/'plugins/kapisch/.codex-plugin';metadata.mkdir(parents=True,exist_ok=True);(metadata/'plugin.json').write_text(json.dumps({'version':json_version}))
  (root/'plugins/kapisch/pyproject.toml').write_text(f'[project]\nversion = "{py_version}"\n')
  (root/'plugins/kapisch/CHANGELOG.md').write_text(f'# Changelog\n\n## {json_version}\n' if changelog else '# Changelog\n')
 def test_unchanged_version_with_shipping_change_fails(self): self.assertEqual(self.run_case().returncode,2)
 def test_increased_version_with_shipping_change_passes(self): self.assertEqual(self.run_case(candidate='1.2.0').returncode,0)
 def test_decreased_version_fails(self): self.assertEqual(self.run_case(candidate='1.0.0').returncode,2)
 def test_metadata_mismatch_fails(self): self.assertEqual(self.run_case(candidate='1.2.0',mismatch=True).returncode,2)
 def test_planning_only_change_needs_no_bump(self): self.assertEqual(self.run_case(changed='docs/superpowers/plans/x.md').returncode,0)
 def test_missing_changelog_entry_fails(self): self.assertEqual(self.run_case(candidate='1.2.0',changelog=False).returncode,2)
