from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def row(variant, tokens=10, turns=1, role="parent", invocation=1):
 return {'run_id':'task','variant':variant,'role':role,'invocation':invocation,'input_tokens':tokens,'output_tokens':2,'cache_read_tokens':None,'turns':turns,'elapsed_ms':5,'workflow_outcome':'complete','validator_exit':0,'review_decision':'approve','review_findings':0,'test_result':'pass','resume_result':'not-applicable'}
def compare(base,candidate):
 with tempfile.TemporaryDirectory() as directory:
  left=Path(directory)/'base.jsonl'; right=Path(directory)/'candidate.jsonl'
  left.write_text(''.join(json.dumps(value)+'\n' for value in base)); right.write_text(''.join(json.dumps(value)+'\n' for value in candidate))
  result=subprocess.run([sys.executable,str(ROOT/'scripts/compare_controller_benchmark.py'),'--baseline',str(left),'--candidate',str(right)],capture_output=True,text=True)
 return result.returncode,json.loads(result.stdout) if result.returncode==0 else result.stdout
class BenchmarkTests(unittest.TestCase):
 def test_unavailable_metrics_never_produce_delta(self):
  for baseline,candidate in ((10,None),(None,8),(None,None)):
   with self.subTest(baseline=baseline,candidate=candidate):
    _,data=compare([row('baseline',baseline)],[row('candidate',candidate)])
    metric=data['roles']['parent']['input_tokens'];self.assertFalse(metric['comparable']);self.assertIsNone(metric['delta']);self.assertFalse(data['required_evidence_present'])
 def test_observed_zero_is_comparable(self):
  _,data=compare([row('baseline',0,0)],[row('candidate',0,0)])
  self.assertEqual(data['roles']['parent']['input_tokens']['delta'],0);self.assertTrue(data['required_evidence_present'])
 def test_mixed_observed_and_unavailable_is_not_comparable(self):
  _,data=compare([row('baseline',10),row('baseline',None,invocation=2)],[row('candidate',8),row('candidate',7,invocation=2)])
  self.assertIsNone(data['roles']['parent']['input_tokens']['delta'])
 def test_missing_parent_is_not_required_evidence(self):
  _,data=compare([row('baseline',role='implementer')],[row('candidate',role='implementer')]);self.assertFalse(data['required_evidence_present'])
 def test_duplicate_records_fail(self):
  code,_=compare([row('baseline'),row('baseline')],[row('candidate')]);self.assertEqual(code,2)
 def test_fully_comparable_data_reports_delta(self):
  _,data=compare([row('baseline',10)],[row('candidate',8)]);self.assertEqual(data['roles']['parent']['input_tokens']['delta'],-2);self.assertTrue(data['required_evidence_present'])
