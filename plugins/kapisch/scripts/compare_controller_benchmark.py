#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
ROLES={"parent","mechanic","implementer-lite","implementer","architect","researcher","reviewer"}
NUMERIC=("input_tokens","output_tokens","cache_read_tokens","turns","elapsed_ms")
REQUIRED={"run_id","variant","role","invocation",*NUMERIC,"workflow_outcome","validator_exit","review_decision","review_findings","test_result","resume_result"}
REQUIRED_COMPARISON={"input_tokens","turns"}
def load(path, variant):
 rows=[]; seen=set()
 for number,line in enumerate(Path(path).read_text().splitlines(),1):
  row=json.loads(line)
  if set(row) != REQUIRED or row["variant"] != variant or row["role"] not in ROLES: raise ValueError(f"bad record {number}")
  key=(row["run_id"],row["role"],row["invocation"])
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
def comparison(base,candidate, role, metric):
 left=base[role][metric]; right=candidate[role][metric]
 comparable=left["observed_count"] > 0 and right["observed_count"] > 0 and not left["unavailable_count"] and not right["unavailable_count"]
 return {"baseline":dict(left, total=left["total"] if left["observed_count"] else None),"candidate":dict(right,total=right["total"] if right["observed_count"] else None),"comparable":comparable,"delta":right["total"]-left["total"] if comparable else None}
def main(argv=None):
 parser=argparse.ArgumentParser(); parser.add_argument("--baseline",required=True); parser.add_argument("--candidate",required=True); parser.add_argument("--format",choices=("json",),default="json"); args=parser.parse_args(argv)
 try: baseline=load(args.baseline,"baseline"); candidate=load(args.candidate,"candidate")
 except (OSError,json.JSONDecodeError,ValueError) as error: print(str(error)); return 2
 base,cand=aggregate(baseline),aggregate(candidate); roles=sorted(set(base)|set(cand)); data={role:{metric:comparison(base,cand,role,metric) for metric in NUMERIC} for role in roles}
 required=all("parent" in values and data["parent"][metric]["comparable"] for values in (base,cand) for metric in REQUIRED_COMPARISON)
 print(json.dumps({"roles":data,"required_evidence_present":required},sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
