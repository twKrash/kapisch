#!/usr/bin/env python3
"""Require a semver decision for material KAPISCH plugin changes."""
from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path
SHIPPED=("plugins/kapisch/skills/","plugins/kapisch/roles/","plugins/kapisch/agents/","plugins/kapisch/kapisch_validation/","plugins/kapisch/scripts/","plugins/kapisch/.codex-plugin/")
VERSION_FILES=("plugins/kapisch/.codex-plugin/plugin.json","plugins/kapisch/pyproject.toml")
def git(*args): return subprocess.check_output(("git",*args),text=True).strip()
def semver(value):
 match=re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)",value)
 if not match: raise ValueError(f"invalid semantic version: {value}")
 return tuple(map(int,match.groups()))
def version_from(text,path):
 if path.endswith(".json"): return json.loads(text)["version"]
 match=re.search(r"^version\s*=\s*\"([^\"]+)\"",text,re.M)
 if not match: raise ValueError(f"missing project version in {path}")
 return match.group(1)
def at(ref,path): return subprocess.check_output(("git","show",f"{ref}:{path}"),text=True)
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--base",required=True,help="base revision to compare");args=parser.parse_args(argv)
 try:
  changed=set(git("diff","--name-only",f"{args.base}...HEAD").splitlines());candidate=[version_from(Path(path).read_text(),path) for path in VERSION_FILES]
  base=[version_from(at(args.base,path),path) for path in VERSION_FILES]
  if candidate[0] != candidate[1]: raise ValueError("plugin.json and pyproject.toml versions differ")
  if base[0] != base[1]: raise ValueError("base plugin versions differ")
  current,previous=semver(candidate[0]),semver(base[0])
  if re.search(rf"^## {re.escape(candidate[0])}\b",Path("plugins/kapisch/CHANGELOG.md").read_text(),re.M) is None: raise ValueError("changelog lacks current version entry")
  material=any(path.startswith(SHIPPED) or path in VERSION_FILES for path in changed)
  if material and current <= previous: raise ValueError("material shipped-plugin change requires increased version")
  if current < previous: raise ValueError("plugin version decreased")
 except (OSError,subprocess.CalledProcessError,ValueError,json.JSONDecodeError) as error:
  print(f"plugin-version-policy: fail: {error}");return 2
 print(f"plugin-version-policy: pass: {base[0]} -> {candidate[0]}; material={material}");return 0
if __name__ == "__main__":raise SystemExit(main())
