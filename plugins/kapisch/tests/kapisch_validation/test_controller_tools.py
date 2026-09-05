from __future__ import annotations
import shutil, subprocess, sys, tempfile, tomllib, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'scripts'))
from migrate_controller_view_v4 import main as migrate_controller_view, migration_disposition
from kapisch_validation.canonical_toml import render_toml
FIXTURES=Path(__file__).parent/'fixtures'
def render(task): return subprocess.run([sys.executable,str(ROOT/'scripts'/'render_controller_view.py'),'--task-dir',str(task)],capture_output=True,text=True)
class ToolTests(unittest.TestCase):
 def test_help(self):
  for name in ('render_controller_view.py','migrate_controller_view_v4.py'):
   self.assertEqual(subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--help']).returncode,0)
 def eligible_v3_source(self, root):
  source=root/'source';shutil.copytree(FIXTURES/'valid-v3-durable',source)
  graph=tomllib.loads((source/'02-execution-graph.toml').read_text())
  v4=tomllib.loads((FIXTURES/'valid-v4-controller/02-execution-graph.toml').read_text())
  for node,v4_node in zip(graph['nodes'],v4['nodes']):
   node['assignment']=v4_node['assignment'];node['assignment']['attempts'][0].pop('outcome_path')
  (source/'02-execution-graph.toml').write_bytes(render_toml(graph))
  return source
 def test_valid_snapshot_renders_atomically(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task)
   self.assertEqual(render(task).returncode,0)
 def test_quoted_state_keys_render_without_duplicates(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';before=state.read_text();after=before.replace('controller_view_path=','"controller_view_path"=').replace('controller_view_sha256=','"controller_view_sha256"=')
   self.assertNotEqual(before,after);state.write_text(after)
   self.assertEqual(render(task).returncode,0)
 def test_literal_quoted_state_keys_render_without_duplicates(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';before=state.read_text();after=before.replace('controller_view_path=',"'controller_view_path'=").replace('controller_view_sha256=',"'controller_view_sha256'=")
   self.assertNotEqual(before,after);state.write_text(after)
   self.assertEqual(render(task).returncode,0)
 def test_escaped_basic_quoted_state_keys_render_without_duplicates(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';before=state.read_text();after=before.replace('controller_view_path=','"controller_view_\\u0070ath"=').replace('controller_view_sha256=','"controller_view_sha\\u0032\\u0035\\u0036"=')
   self.assertNotEqual(before,after);state.write_text(after)
   self.assertEqual(render(task).returncode,0)
 def test_multiline_state_bindings_render_without_residue(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';before=state.read_text();after=before.replace('controller_view_path="04-controller-view.toml"','controller_view_path="""\\\n04-controller-view.toml"""').replace('controller_view_sha256="796c118279979cb80e20179470af63b24a087442b91b741f5bdef08a6f490fdf"','controller_view_sha256="""\\\n796c118279979cb80e20179470af63b24a087442b91b741f5bdef08a6f490fdf"""')
   self.assertNotEqual(before,after);state.write_text(after)
   self.assertEqual(render(task).returncode,0)
 def test_multiline_root_value_with_table_syntax_renders(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';manifest=task/'02-execution-graph.toml';before=state.read_text();after=before.replace('task_id = "valid"','task_id = """\\\n[valid]"""');self.assertNotEqual(before,after);state.write_text(after);manifest.write_text(manifest.read_text().replace('task_id = "valid"','task_id = "[valid]"'))
   for outcome in (task/'stage-outcomes').iterdir(): outcome.write_text(outcome.read_text().replace('task_id = "valid"','task_id = "[valid]"'))
   self.assertEqual(render(task).returncode,0)
 def test_literal_root_value_with_backslash_preserves_table_boundary(self):
  with tempfile.TemporaryDirectory() as directory:
   task=Path(directory)/'task';shutil.copytree(FIXTURES/'valid-v4-controller',task);state=task/'03-state.toml';manifest=task/'02-execution-graph.toml';before=state.read_text();after=before.replace('task_id = "valid"',"task_id = 'abc\\'")+'\n[extensions."com.example"]\ncontroller_view_path = "unrelated"\n';self.assertNotEqual(before,after);state.write_text(after)
   manifest.write_text(manifest.read_text().replace('task_id = "valid"','task_id = "abc\\\\"'))
   for outcome in (task/'stage-outcomes').iterdir(): outcome.write_text(outcome.read_text().replace('task_id = "valid"','task_id = "abc\\\\"'))
   self.assertEqual(render(task).returncode,0);self.assertEqual(tomllib.loads(state.read_text())["extensions"]["com.example"]["controller_view_path"],"unrelated")
 def test_migration_rejects_preexisting_outcome_directory(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'source';destination=root/'destination';shutil.copytree(FIXTURES/'valid-v3-durable',source);outcomes=source/'stage-outcomes';outcomes.mkdir();(outcomes/'old.txt').write_text('old')
   self.assertEqual(migrate_controller_view(['--task-dir',str(source),'--destination-task-dir',str(destination),'--approve']),2);self.assertFalse(destination.exists())
 def test_migration_containment_preserves_source_and_outside_files(self):
  for attempt_id,target_name in (('../../../escaped','escaped.toml'),('../../../source/02-execution-graph','02-execution-graph.toml'),('CON','con-sentinel.toml')):
   with self.subTest(attempt_id=attempt_id),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);source=self.eligible_v3_source(root);destination=root/'destination';sentinel=root/target_name;sentinel.write_bytes(b'sentinel')
    graph=tomllib.loads((source/'02-execution-graph.toml').read_text());graph['nodes'][0]['assignment']['attempts'][0]['id']=attempt_id
    (source/'02-execution-graph.toml').write_bytes(render_toml(graph))
    before={path.relative_to(source):path.read_bytes() for path in source.rglob('*') if path.is_file()}
    self.assertEqual(migrate_controller_view(['--task-dir',str(source),'--destination-task-dir',str(destination),'--approve']),2)
    self.assertFalse(destination.exists());self.assertEqual(sentinel.read_bytes(),b'sentinel')
    self.assertEqual(before,{path.relative_to(source):path.read_bytes() for path in source.rglob('*') if path.is_file()})
 def test_migration_rejects_unsupported_state_values_without_writes(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=self.eligible_v3_source(root);destination=root/'destination'
   state=source/'03-state.toml';state.write_text(state.read_text()+'\\n[extensions."com.example"]\\nrecorded_at = 2026-09-02T12:00:00Z\\n')
   before={path.relative_to(source):path.read_bytes() for path in source.rglob('*') if path.is_file()}
   self.assertEqual(migrate_controller_view(['--task-dir',str(source),'--destination-task-dir',str(destination),'--approve']),2)
   self.assertFalse(destination.exists());self.assertEqual(before,{path.relative_to(source):path.read_bytes() for path in source.rglob('*') if path.is_file()})
 def test_eligible_migration_preserves_canonical_verification(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=self.eligible_v3_source(root);destination=root/'destination'
   self.assertEqual(migrate_controller_view(['--task-dir',str(source),'--destination-task-dir',str(destination),'--approve']),0)
   outcome=tomllib.loads((destination/'stage-outcomes/AT-T01-1.toml').read_text())
   graph=tomllib.loads((destination/'02-execution-graph.toml').read_text())
   self.assertEqual(outcome['verification'],[{key:graph['nodes'][0]['verification_evidence'][0][key] for key in ('check','result','evidence_ref','output_sha256')}])
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
