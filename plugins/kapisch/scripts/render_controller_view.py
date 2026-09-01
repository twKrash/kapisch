#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, os, re, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from kapisch_validation.cli import validate_snapshot
from kapisch_validation.controller_view import _outcome_records, build_controller_view, render_controller_view
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state

def atomic(path: Path, data: bytes) -> None:
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--task-dir',required=True,type=Path); a=p.parse_args(argv); d=a.task_dir.resolve()
    parsed=parse_manifest(d/'02-execution-graph.toml'); state,state_errors=parse_state(d/'03-state.toml')
    contract_dir=ROOT/'skills'/'kapisch'
    if parsed.manifest is None or state is None or parsed.manifest.version != 4 or parsed.errors or state_errors:
        return 2
    if validate_snapshot(parsed.manifest,state,d,contract_dir,include_controller_view=False):
        return 2
    view=render_controller_view(build_controller_view(parsed.manifest,state,_outcome_records(parsed.manifest,d),(d/'02-execution-graph.toml').read_bytes()))
    old_state=(d/'03-state.toml').read_bytes(); old_view=(d/'04-controller-view.toml').read_bytes() if (d/'04-controller-view.toml').exists() else None
    text=old_state.decode('utf-8'); digest=hashlib.sha256(view).hexdigest()
    for key,value in [('controller_view_path','04-controller-view.toml'),('controller_view_sha256',digest)]:
        text,count=re.subn(rf'^(?:"{key}"|{key})\s*=.*$',f'"{key}" = "{value}"',text,flags=re.M)
        if not count: text += ('\n' if not text.endswith('\n') else '')+f'{key}="{value}"\n'
    try:
        atomic(d/'04-controller-view.toml',view); atomic(d/'03-state.toml',text.encode())
        rebound=parse_manifest(d/'02-execution-graph.toml'); rebound_state,rebound_state_errors=parse_state(d/'03-state.toml')
        if rebound.manifest is None or rebound_state is None or rebound.errors or rebound_state_errors or validate_snapshot(rebound.manifest,rebound_state,d,contract_dir):
            raise ValueError("rendered snapshot does not validate")
    except BaseException:
        if old_view is not None: atomic(d/'04-controller-view.toml',old_view)
        else:
            try: (d/'04-controller-view.toml').unlink()
            except FileNotFoundError: pass
        atomic(d/'03-state.toml',old_state); return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
