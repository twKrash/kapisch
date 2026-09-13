# Deterministic generated artifacts

KAPISCH 2.1.0 defines deterministic bytes for KAPISCH-owned generated outputs
when the logical input is fixed. This contract applies to canonical new writes;
tolerant reads continue to accept compatible historical formatting.

## Canonical portable outputs

Sanctioned TOML, JSON, text, profile, route, outcome, knowledge, presentation,
and controller-view writers emit UTF-8 without a BOM, LF newlines, and the
artifact's declared final-newline rule. Closed fields use their declared order.
Collections are sorted only when their contract defines them as unordered;
ordered history remains in supplied order.

Concrete paths in portable artifacts are relative POSIX paths rooted at the
artifact's declared task or repository root. Opaque identifiers and external
references are not reinterpreted as filesystem paths. The durable manifests v1-v4
remain readable, and each version's writer accepts only fields legal for that
version.

A semantically current artifact is a no-op: there is no formatting-only rewrite.
Canonicalization is a write boundary, not a bulk conversion command for existing
repositories.

## Exact and machine-local data

Reports and verification attachments are exact persisted evidence bytes. Their
digests are calculated from bytes on disk; newline or encoding changes alter the
digest and are never normalized away.

Profile ownership records and recovery journals intentionally retain
machine-local native paths, process IDs, and switch tokens. These records are
truthful local state rather than relocatable output. Generated profile content
is canonical, but the local ownership record is outside the portable-artifact
digest vector.

Runtime measurements and diagnostics may vary with observed execution. They do
not become workflow authority merely because their envelope is encoded
canonically.

## Compatibility and migration

No durable schema version, field meaning, or digest domain changes in 2.1.0.
Profile-state schema 1, switch-journal schema 3, outcome schema 1,
controller-view version 1, route schema 1, reviewer-invocation compatibility,
and knowledge-ledger version 1 remain unchanged.

The explicit v3-to-v4 migration copies and validates its source. A legacy
concrete path that cannot be represented by the canonical v4 writer is rejected
with a diagnostic; the source remains untouched and no destination is
published.

## Verification

The committed deterministic digest vector is exercised from relocated roots,
multiple working directories, two Python hash seeds, available locale and time
zone variants, Linux, and native Windows. See the
[acceptance matrix](acceptance.md) and
[2.1.0 Windows record](acceptance-windows-v2.1.0.md).
