#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
ROLES={'parent','mechanic','implementer-lite','implementer','architect','researcher','reviewer'}
NUMERIC=('input_tokens','output_tokens','cache_read_tokens','turns','elapsed_ms')
REQUIRED={'run_id','variant','role','invocation',*NUMERIC,'workflow_outcome','validator_exit','review_decision','review_findings','test_result','resume_result'}
def load(path,variant):
 rows=[]; seen=set()
 for n,line in enumerate(Path(path).read_text().splitlines(),1):
  row=json.loads(line)
  if set(row)!=REQUIRED or row['variant']!=variant or row['role'] not in ROLES: raise ValueError(f'bad record {n}')
  key=(row['run_id'],row['role'],row['invocation'])
  if key in seen: raise ValueError(f'duplicate {key}')
  seen.add(key)
  if any(v is not None and (not isinstance(v,int) or v<0) for v in (row[k] for k in NUMERIC)): raise ValueError(f'bad numeric {n}')
  rows.append(row)
 return rows
def totals(rows):
 out={}
 for row in rows:
  role=out.setdefault(row['role'],{k:0 for k in NUMERIC})
  for k in NUMERIC:
   if row[k] is not None: role[k]+=row[k]
 return out
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--candidate',required=True);p.add_argument('--format',choices=('json',),default='json');a=p.parse_args(argv)
 try: base=load(a.baseline,'baseline'); cand=load(a.candidate,'candidate')
 except (OSError,json.JSONDecodeError,ValueError) as e: print(str(e));return 2
 bt,ct=totals(base),totals(cand); roles=sorted(set(bt)|set(ct)); summary={r:{k:{'baseline':bt.get(r,{}).get(k),'candidate':ct.get(r,{}).get(k),'delta':ct.get(r,{}).get(k,0)-bt.get(r,{}).get(k,0)} for k in NUMERIC} for r in roles}
 print(json.dumps({'roles':summary,'required_evidence_present':True},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
