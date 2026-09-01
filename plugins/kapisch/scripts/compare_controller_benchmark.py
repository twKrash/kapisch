#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
ROLES={"parent","mechanic","implementer-lite","implementer","architect","researcher","reviewer"}
NUMERIC=("input_tokens","output_tokens","cache_read_tokens","turns","elapsed_ms")
REQUIRED={"run_id","scenario","variant","role","invocation",*NUMERIC,"workflow_outcome","validator_exit","review_decision","review_findings","test_result","resume_result"}
REQUIRED_COMPARISON={"input_tokens","turns"}
def load(path, variant):
 rows=[]; seen=set()
 for number,line in enumerate(Path(path).read_text().splitlines(),1):
  row=json.loads(line)
  if not isinstance(row,dict) or set(row) != REQUIRED: raise ValueError(f"bad record {number}")
  if any(not isinstance(row[field],str) or not row[field] for field in ("run_id","scenario","role","workflow_outcome","review_decision","test_result","resume_result")) or row["variant"] != variant or row["role"] not in ROLES or row["scenario"] not in {"behavioral","durable-fix","worker-reviewer-resume"} or not isinstance(row["invocation"],int) or isinstance(row["invocation"],bool) or row["invocation"] < 1 or not isinstance(row["validator_exit"],int) or isinstance(row["validator_exit"],bool) or row["validator_exit"] < 0 or not isinstance(row["review_findings"],int) or isinstance(row["review_findings"],bool) or row["review_findings"] < 0: raise ValueError(f"bad record {number}")
  key=(row["run_id"],row["scenario"],row["role"],row["invocation"])
  if key in seen: raise ValueError(f"duplicate {key}")
  seen.add(key)
  if any(value is not None and (not isinstance(value,int) or isinstance(value,bool) or value < 0) for value in (row[key] for key in NUMERIC)): raise ValueError(f"bad numeric {number}")
  rows.append(row)
 return rows
def aggregate(rows):
 result=defaultdict(lambda: defaultdict(lambda:{"observed_count":0,"unavailable_count":0,"total":0}))
 for row in rows:
  for metric in NUMERIC:
   value=row[metric]; summary=result[row["role"]][metric]
   if value is None: summary["unavailable_count"] += 1
   else: summary["observed_count"] += 1; summary["total"] += value
 return result
def comparison(base,candidate, role, metric, pairing_complete):
 left=base[role][metric]; right=candidate[role][metric]
 comparable=pairing_complete and left["observed_count"] > 0 and right["observed_count"] > 0 and not left["unavailable_count"] and not right["unavailable_count"]
 return {"baseline":dict(left, total=left["total"] if left["observed_count"] else None),"candidate":dict(right,total=right["total"] if right["observed_count"] else None),"comparable":comparable,"delta":right["total"]-left["total"] if comparable else None}
def covered_per_run(rows, predicate):
 runs=defaultdict(list)
 for row in rows: runs[row["run_id"]].append(row)
 return bool(runs) and all(predicate(run) for run in runs.values())
def behavioral_coverage(rows):
 return {"parent","researcher","implementer","reviewer"} <= {row["role"] for row in rows} and {"approve","ready"} <= {row["review_decision"] for row in rows if row["role"] == "reviewer"}
def durable_coverage(rows):
 blocking=[row for row in rows if row["role"] == "reviewer" and row["review_decision"] == "do-not-approve" and row["review_findings"] > 0]
 lifecycle=any(
  any(row["role"] == "implementer" and row["invocation"] < blocked["invocation"] for row in rows)
  and any(
   fix["role"] == "implementer" and fix["invocation"] > blocked["invocation"]
   and any(
    review["role"] == "reviewer" and review["review_decision"] == "approve" and review["invocation"] > fix["invocation"]
    and any(ready["role"] == "reviewer" and ready["review_decision"] == "ready" and ready["invocation"] > review["invocation"] for ready in rows)
    for review in rows
   )
   for fix in rows
  )
  for blocked in blocking
 )
 return {"parent","researcher","implementer","reviewer"} <= {row["role"] for row in rows} and lifecycle
def resume_coverage(rows):
 return {"parent","implementer","reviewer"} <= {row["role"] for row in rows} and all(any(row["role"] == role and row["resume_result"] == "pass" for row in rows) for role in {"implementer","reviewer"})
def coverage(rows):
 scenarios={scenario:[row for row in rows if row["scenario"] == scenario] for scenario in {"behavioral","durable-fix","worker-reviewer-resume"}}
 return covered_per_run(scenarios["behavioral"],behavioral_coverage) and covered_per_run(scenarios["durable-fix"],durable_coverage) and covered_per_run(scenarios["worker-reviewer-resume"],resume_coverage)
def main(argv=None):
 parser=argparse.ArgumentParser(); parser.add_argument("--baseline",required=True); parser.add_argument("--candidate",required=True); parser.add_argument("--format",choices=("json",),default="json"); args=parser.parse_args(argv)
 try: baseline=load(args.baseline,"baseline"); candidate=load(args.candidate,"candidate")
 except (OSError,json.JSONDecodeError,ValueError) as error: print(str(error)); return 2
 base,cand=aggregate(baseline),aggregate(candidate)
 base_keys={(row["run_id"],row["scenario"],row["role"],row["invocation"]) for row in baseline}; candidate_keys={(row["run_id"],row["scenario"],row["role"],row["invocation"]) for row in candidate}
 unmatched_baseline=sorted(base_keys-candidate_keys); unmatched_candidate=sorted(candidate_keys-base_keys); pairing_complete=not unmatched_baseline and not unmatched_candidate
 roles=sorted(set(base)|set(cand)); data={role:{metric:comparison(base,cand,role,metric,pairing_complete) for metric in NUMERIC} for role in roles}
 semantic_evidence_present=all(
  row["workflow_outcome"] == "complete" and row["validator_exit"] == 0
  and row["test_result"] == "pass" and row["resume_result"] in {"pass","not-applicable"}
  and row["review_decision"] in {"approve","do-not-approve","ready"} and isinstance(row["review_findings"],int) and not isinstance(row["review_findings"],bool) and row["review_findings"] >= 0
  for row in (*baseline,*candidate)
 )
 coverage_complete=all(coverage(rows) for rows in (baseline,candidate))
 required=pairing_complete and coverage_complete and semantic_evidence_present and all(data[role][metric]["comparable"] for role in roles for metric in REQUIRED_COMPARISON)
 print(json.dumps({"roles":data,"required_evidence_present":required,"semantic_evidence_present":semantic_evidence_present,"coverage_complete":coverage_complete,"pairing_complete":pairing_complete,"unmatched_baseline":unmatched_baseline,"unmatched_candidate":unmatched_candidate},sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
