from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class BenchmarkTests(unittest.TestCase):
 def test_comparator_reports_role_delta(self):
  record={'run_id':'task','variant':'baseline','role':'parent','invocation':1,'input_tokens':10,'output_tokens':2,'cache_read_tokens':None,'turns':1,'elapsed_ms':5,'workflow_outcome':'complete','validator_exit':0,'review_decision':'approve','review_findings':0,'test_result':'pass','resume_result':'not-applicable'}
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)/'base.jsonl'; cand=Path(d)/'cand.jsonl'; base.write_text(json.dumps(record)+'\n'); record['variant']='candidate';record['input_tokens']=8;cand.write_text(json.dumps(record)+'\n')
   result=subprocess.run([sys.executable,str(ROOT/'scripts/compare_controller_benchmark.py'),'--baseline',str(base),'--candidate',str(cand)],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['roles']['parent']['input_tokens']['delta'],-2)
