from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def row(variant, tokens=10, turns=1, role="parent", invocation=1, scenario="behavioral", decision="approve", resume="not-applicable", findings=0):
 return {'run_id':'task','scenario':scenario,'variant':variant,'role':role,'invocation':invocation,'input_tokens':tokens,'output_tokens':2,'cache_read_tokens':None,'turns':turns,'elapsed_ms':5,'workflow_outcome':'complete','validator_exit':0,'review_decision':decision,'review_findings':findings,'test_result':'pass','resume_result':resume}
def complete(variant,tokens=10):
 return [
  row(variant,tokens,scenario="behavioral"),row(variant,role="researcher",scenario="behavioral"),row(variant,role="implementer",scenario="behavioral"),row(variant,role="reviewer",scenario="behavioral",decision="approve",invocation=1),row(variant,role="reviewer",scenario="behavioral",decision="ready",invocation=2),
  row(variant,tokens,scenario="durable-fix"),row(variant,role="researcher",scenario="durable-fix"),row(variant,role="implementer",scenario="durable-fix",invocation=1),row(variant,role="reviewer",scenario="durable-fix",decision="do-not-approve",findings=1,invocation=1),row(variant,role="implementer",scenario="durable-fix",invocation=2),row(variant,role="reviewer",scenario="durable-fix",decision="approve",invocation=3),row(variant,role="reviewer",scenario="durable-fix",decision="ready",invocation=4),
  row(variant,tokens,scenario="worker-reviewer-resume"),row(variant,role="implementer",scenario="worker-reviewer-resume",resume="pass"),row(variant,role="reviewer",scenario="worker-reviewer-resume",resume="pass")
 ]
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
  _,data=compare(complete('baseline',0),complete('candidate',0))
  self.assertEqual(data['roles']['parent']['input_tokens']['delta'],0);self.assertTrue(data['required_evidence_present'])
 def test_mixed_observed_and_unavailable_is_not_comparable(self):
  _,data=compare([row('baseline',10),row('baseline',None,invocation=2)],[row('candidate',8),row('candidate',7,invocation=2)])
  self.assertIsNone(data['roles']['parent']['input_tokens']['delta'])
 def test_missing_parent_is_not_required_evidence(self):
  _,data=compare([row('baseline',role='implementer')],[row('candidate',role='implementer')]);self.assertFalse(data['required_evidence_present'])
 def test_omitted_expensive_child_blocks_comparison(self):
  _,data=compare([row('baseline',10),row('baseline',100,role='implementer')],[row('candidate',8)])
  self.assertFalse(data['pairing_complete']);self.assertFalse(data['required_evidence_present']);self.assertIsNone(data['roles']['parent']['input_tokens']['delta']);self.assertEqual(data['unmatched_baseline'],[['task','behavioral','implementer',1]])
 def test_duplicate_records_fail(self):
  code,_=compare([row('baseline'),row('baseline')],[row('candidate')]);self.assertEqual(code,2)
 def test_failed_run_evidence_is_not_accepted(self):
  baseline=row('baseline');candidate=row('candidate');candidate['validator_exit']=2;candidate['test_result']='fail'
  _,data=compare([baseline],[candidate]);self.assertFalse(data['semantic_evidence_present']);self.assertFalse(data['required_evidence_present'])
 def test_fully_comparable_data_reports_delta(self):
  _,data=compare(complete('baseline',10),complete('candidate',8));self.assertEqual(data['roles']['parent']['input_tokens']['delta'],-6);self.assertTrue(data['required_evidence_present'])
 def test_durable_evidence_requires_a_blocking_fix_cycle(self):
  missing={
   'blocking':lambda row:row['role'] == 'reviewer' and row['review_decision'] == 'do-not-approve',
   'fixing':lambda row:row['role'] == 'implementer' and row['invocation'] == 2,
   'rereview':lambda row:row['role'] == 'reviewer' and row['review_decision'] == 'approve' and row['invocation'] == 3,
   'readiness':lambda row:row['role'] == 'reviewer' and row['review_decision'] == 'ready' and row['invocation'] == 4,
  }
  for phase,remove in missing.items():
   with self.subTest(phase=phase):
    baseline=[row for row in complete('baseline') if not remove(row)];candidate=[row for row in complete('candidate') if not remove(row)]
    _,data=compare(baseline,candidate)
    self.assertFalse(data['coverage_complete']);self.assertFalse(data['required_evidence_present'])
