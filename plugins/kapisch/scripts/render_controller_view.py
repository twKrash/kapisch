#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, os, re, sys, tempfile, tomllib
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
ROOT_ASSIGNMENT=re.compile(r'^[ \t]*(?P<key>(?:[A-Za-z0-9_-]+|"(?:\\.|[^"\\])*"|\'[^\']*\'))[ \t]*=',re.M)
def binding_value_end(root: str, start: int) -> int:
    start+=len(root[start:])-len(root[start:].lstrip(" \t"))
    delimiter=next((value for value in ('"""',"'''",'"',"'") if root.startswith(value,start)),None)
    if delimiter is None:
        end=root.find("\n",start)
        return len(root) if end < 0 else end
    index=start+len(delimiter)
    while index < len(root):
        if root.startswith(delimiter,index): return index+len(delimiter)
        if delimiter != "'''" and root[index] == "\\": index+=2
        else: index+=1
    return len(root)
def replace_root_binding(root: str, key: str, value: str) -> str | None:
    matches=[]
    for match in ROOT_ASSIGNMENT.finditer(root):
        try: parsed=tomllib.loads(f"{match.group('key')} = 0")
        except tomllib.TOMLDecodeError: continue
        if set(parsed) == {key}: matches.append(match)
    if len(matches) != 1: return None
    match=matches[0]
    return root[:match.start()]+f'"{key}" = "{value}"'+root[binding_value_end(root,match.end()):]
def first_table_offset(text: str) -> int | None:
    index=line_start=array_depth=0
    while index < len(text):
        if text[index] == "#":
            newline=text.find("\n",index)
            index=len(text) if newline < 0 else newline
        elif text.startswith('"""',index) or text.startswith("'''",index):
            index=binding_value_end(text,index)
        elif text[index] in ('"',"'"):
            index=binding_value_end(text,index)
        elif text[index] == "[":
            if array_depth == 0 and not text[line_start:index].strip(): return index
            array_depth+=1; index+=1
        elif text[index] == "]":
            array_depth=max(0,array_depth-1); index+=1
        else:
            if text[index] == "\n": line_start=index+1
            index+=1
    return None

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
    first_table=first_table_offset(text); root=text[:first_table] if first_table is not None else text; tables=text[first_table:] if first_table is not None else ''
    for key,value in [('controller_view_path','04-controller-view.toml'),('controller_view_sha256',digest)]:
        root=replace_root_binding(root,key,value)
        if root is None: return 2
    text=root+tables
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
