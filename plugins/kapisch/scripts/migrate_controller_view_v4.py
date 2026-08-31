#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, os, shutil, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from kapisch_validation.canonical_toml import render_toml
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state
from kapisch_validation.cli import validate
from render_controller_view import main as render

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main(argv=None):
 p=argparse.ArgumentParser(); p.add_argument('--task-dir',required=True,type=Path); p.add_argument('--destination-task-dir',required=True,type=Path); p.add_argument('--approve',action='store_true'); a=p.parse_args(argv)
 if not a.approve: p.error('migration requires explicit --approve')
 src=a.task_dir.resolve(); dst=a.destination_task_dir.resolve()
 if not src.is_dir() or dst.exists() or src==dst: return 2
 m=parse_manifest(src/'02-execution-graph.toml').manifest; s,e=parse_state(src/'03-state.toml')
 if m is None or s is None or m.version!=3 or s.workflow_status!='complete' or validate(ROOT/'skills/kapisch',src): return 2
 dst.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(dir=dst.parent,prefix='kapisch-v4-') as tmp:
  stage=Path(tmp)/dst.name; shutil.copytree(src,stage,copy_function=shutil.copy2); raw=dict(m.raw); raw['version']=4; raw['controller_view']='04-controller-view.toml'; (stage/'stage-outcomes').mkdir()
  for node in raw['nodes']:
   assignment=node.get('assignment'); attempts=assignment.get('attempts') if isinstance(assignment,dict) else None
   if not isinstance(attempts,list) or not attempts: return 2
   for attempt in attempts:
    if not isinstance(attempt,dict) or attempt.get('status') not in {'complete','blocked','failed'}: return 2
    aid=attempt.get('id'); path=f'stage-outcomes/{aid}.toml'; attempt['outcome_path']=path; report=stage/node['report']; role=node['executor_class']; inv=node.get('reviewer_invocation'); invraw={}
    if role=='reviewer':
     if not isinstance(inv,str) or not (stage/inv).is_file(): return 2
     import tomllib; invraw=tomllib.loads((stage/inv).read_text())
    out={'version':1,'task_id':m.task_id,'node_id':node['id'],'role':role,'assignment_id':assignment['id'],'attempt_id':aid,'lifecycle':attempt['status'],'role_status':'done' if attempt['status']=='complete' else attempt['status'],'base_revision':node['revision']['base'],'head_revision':node['revision']['head'],'working_tree_state_sha256':'unavailable','report_path':node['report'],'report_sha256':digest(report),'invocation_path':inv if role=='reviewer' else 'unavailable','invocation_id':invraw.get('invocation_id','unavailable') if role=='reviewer' else 'unavailable','invocation_sha256':digest(stage/inv) if role=='reviewer' else 'unavailable','reviewer_decision':invraw.get('returned_decision','unavailable') if role=='reviewer' else 'unavailable','redispatch_reason':'none','predecessor_attempt_id':'unavailable','retry_budget_delta':0,'next_action_reason':'completed','findings':[],'verification':[]}
    (stage/path).write_bytes(render_toml(out))
  (stage/'02-execution-graph.toml').write_bytes(render_toml(raw,key_order=('version','task_id','source_plan','roadmap_item','base_revision','controller_view','policies','nodes')))
  state=dict(s.raw); state['controller_view_path']='04-controller-view.toml'; state['controller_view_sha256']='0'*64; (stage/'03-state.toml').write_bytes(render_toml(state))
  if render(['--task-dir',str(stage)]): return 2
  if validate(ROOT/'skills/kapisch',stage): return 2
  os.replace(stage,dst)
 return 0
if __name__=='__main__': raise SystemExit(main())
