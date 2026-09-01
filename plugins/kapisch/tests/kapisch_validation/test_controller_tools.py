from __future__ import annotations
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'scripts'))
from migrate_controller_view_v4 import migration_disposition
FIXTURES=Path(__file__).parent/'fixtures'
def render(task): return subprocess.run([sys.executable,str(ROOT/'scripts'/'render_controller_view.py'),'--task-dir',str(task)],capture_output=True,text=True)
class ToolTests(unittest.TestCase):
 def test_help(self):
  for name in ('render_controller_view.py','migrate_controller_view_v4.py'):
   self.assertEqual(subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--help']).returncode,0)
 def test_valid_snapshot_renders_atomically(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task)
   self.assertEqual(render(task).returncode,0)
 def test_quoted_state_keys_render_without_duplicates(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';state.write_text(state.read_text().replace('controller_view_path =','"controller_view_path" =').replace('controller_view_sha256 =','"controller_view_sha256" ='))
   self.assertEqual(render(task).returncode,0)
 def test_indented_root_keys_ignore_indented_extension_keys(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml'
   state.write_text(state.read_text().replace('controller_view_path =','  controller_view_path =').replace('controller_view_sha256 =','  controller_view_sha256 =')+'\n  [extensions."com.example"]\n  controller_view_path = "extension"\n')
   self.assertEqual(render(task).returncode,0)
 def test_invalid_canonical_snapshots_are_untouched(self):
  for fixture in ('invalid-v4-report-digest','invalid-v4-reviewer-invocation'):
   with self.subTest(fixture=fixture),tempfile.TemporaryDirectory() as directory:
    task=Path(directory)/'task';shutil.copytree(FIXTURES/fixture,task);before={path.relative_to(task):path.read_bytes() for path in (task/'03-state.toml',task/'04-controller-view.toml')}
    self.assertNotEqual(render(task).returncode,0)
    self.assertEqual(before,{path.relative_to(task):path.read_bytes() for path in (task/'03-state.toml',task/'04-controller-view.toml')})
    self.assertFalse(any(path.name.startswith('.04-controller-view.toml.') for path in task.iterdir()))
 def test_v4_delegation_evidence_is_validated(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);(task/'delegations/D01/00-context.md').unlink()
   result=subprocess.run([sys.executable,str(ROOT/'scripts'/'validate_kapisch.py'),'--task-dir',str(task)],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('TWV-DELEG-MISSING-EVIDENCE',result.stdout)
 def test_missing_outcome_is_untouched(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);next((task/'stage-outcomes').iterdir()).unlink();before=(task/'03-state.toml').read_bytes(),(task/'04-controller-view.toml').read_bytes()
   self.assertNotEqual(render(task).returncode,0);self.assertEqual(before,((task/'03-state.toml').read_bytes(),(task/'04-controller-view.toml').read_bytes()))
 def test_migration_rejects_conflicting_disposition_fields(self):
  with tempfile.TemporaryDirectory() as directory:
   report=Path(directory)/'report.md'
   report.write_text('status: DONE_WITH_CONCERNS\nconcerns: security finding\nfindings: F01\nstatus: DONE\nconcerns: none\nfindings: none\n')
   self.assertFalse(migration_disposition(report))
 def test_migration_rejects_malformed_disposition_marker(self):
  with tempfile.TemporaryDirectory() as directory:
   report=Path(directory)/'report.md'
   report.write_text('status\nstatus: DONE\nconcerns: none\nfindings: none\n')
   self.assertFalse(migration_disposition(report))
