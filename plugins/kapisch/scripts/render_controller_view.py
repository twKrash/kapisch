#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import os
import stat
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from kapisch_validation.cli import validate_snapshot
from kapisch_validation.controller_view import _outcome_records, build_controller_view, render_controller_view
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state, render_state

def atomic(path: Path, data: bytes) -> None:
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def _existing_view_bytes(path: Path) -> bytes | None:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("existing controller view is not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--task-dir',required=True,type=Path); a=p.parse_args(argv); d=a.task_dir.resolve()
    parsed=parse_manifest(d/'02-execution-graph.toml'); state,state_errors=parse_state(d/'03-state.toml')
    contract_dir=ROOT/'skills'/'kapisch'
    if parsed.manifest is None or state is None or parsed.manifest.version != 4 or parsed.errors or state_errors:
        return 2
    if validate_snapshot(parsed.manifest,state,d,contract_dir,include_controller_view=False):
        return 2
    view=render_controller_view(build_controller_view(parsed.manifest,state,_outcome_records(parsed.manifest,d),(d/'02-execution-graph.toml').read_bytes()))
    try:
        old_state = (d / "03-state.toml").read_bytes()
        old_view = _existing_view_bytes(d / "04-controller-view.toml")
    except OSError:
        return 2
    expected_path = "04-controller-view.toml"
    expected_digest = hashlib.sha256(view).hexdigest()
    binding_is_current = (
        state.controller_view_path == expected_path
        and state.controller_view_sha256 == expected_digest
    )
    view_changed = old_view != view
    state_changed = not binding_is_current
    if not view_changed and not state_changed:
        publication = "noop"
    elif not state_changed:
        publication = "view_only"
    else:
        publication = "view_and_state"
    if publication == "noop":
        return 0

    rendered_state = old_state
    if publication == "view_and_state":
        state_raw = dict(state.raw)
        state_raw["controller_view_path"] = expected_path
        state_raw["controller_view_sha256"] = expected_digest
        try:
            rendered_state = render_state(state_raw)
        except ValueError:
            return 2
    published_view = False
    published_state = False
    try:
        if view_changed:
            atomic(d/'04-controller-view.toml',view)
            published_view = True
        if state_changed:
            atomic(d/'03-state.toml',rendered_state)
            published_state = True
        rebound=parse_manifest(d/'02-execution-graph.toml'); rebound_state,rebound_state_errors=parse_state(d/'03-state.toml')
        if rebound.manifest is None or rebound_state is None or rebound.errors or rebound_state_errors or validate_snapshot(rebound.manifest,rebound_state,d,contract_dir):
            raise ValueError("rendered snapshot does not validate")
    except BaseException:
        if published_view:
            if old_view is not None: atomic(d/'04-controller-view.toml',old_view)
            else:
                try: (d/'04-controller-view.toml').unlink()
                except FileNotFoundError: pass
        if published_state:
            atomic(d/'03-state.toml',old_state)
        return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
