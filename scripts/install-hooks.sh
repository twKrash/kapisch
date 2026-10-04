#!/bin/sh
set -eu

git rev-parse --show-toplevel >/dev/null
git config core.hooksPath .githooks
printf 'Configured Git hooks path: .githooks\n'
