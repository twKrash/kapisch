# Deterministic Generated Artifacts — Spec Authoring Plan

## Context

KAPISCH 2.0.0 at `main` commit `265f37c` established a deliberate compatibility boundary for managed profiles: profile-state schema 1 and switch-journal schema 3 are current; older profile/setup state is rejected without automatic migration or recovery. Durable run compatibility remains independently versioned through manifest versions 1–4 and must not change incidentally.

Next phase defines which KAPISCH-generated artifacts can promise semantic, serialization, cross-platform, regeneration, and relocation determinism. Design must distinguish canonical output from intentionally variable durable evidence and ephemeral transaction state. Deliverable is architectural specification only; no implementation plan or production change.

Repository exploration covered:

- `plugins/kapisch/scripts/setup_profile.py` and profile safety tests;
- `canonical_toml.py`, `artifact_io.py`, controller-view/outcome code, render/migration scripts, validators, fixtures, and behavioral tests;
- durable graph/state, handoff, review, delegation, resume, knowledge, metrics, and project-understanding contracts;
- PR #26 thin-controller history, PR #37 compatibility-reset history/spec, current open determinism/recovery issues, portable-package behavior, and version policy.

Key findings:

- Managed profile bytes already normalize source CRLF/CR to LF before validation, hashing, and rendering.
- Profile-state records use fixed UTF-8/LF field output but intentionally contain exact native absolute installation paths.
- Journal schema 3 contains exact native paths and random-token recovery paths; lock PID and temporary names are runtime/transaction data.
- `render_toml` already provides a small deterministic standard-library encoder: quoted keys/strings, sorted nested maps, finite values, UTF-8, and terminal LF. Root ordering remains caller-controlled.
- Controller views are canonical derived projections. Manifest source binding hashes exact manifest bytes; state source binding hashes parsed semantic state after removing view bindings.
- Durable controller-authored TOML has strict schemas but no single enforced writer. Several list-order semantics are currently distributed across prose and validators.
- Review/delegation/report digests bind exact persisted bytes. Git-state digests bind exact raw Git command output. These must not be silently newline-normalized.
- Legacy durable migration is intentionally byte-preserving. v3→v4 migration canonicalizes graph/state/outcomes but preserves copied detailed evidence.
- Natural-language handoffs, reports, plans, dates, and runtime metrics contain genuine event/prose variability; they cannot receive the same byte-identity guarantee as machine projections.
- Static validator fixtures are committed contract examples, not runtime-generated artifacts; `.gitattributes` pins them to LF because exact-byte digest relationships exist.

## Approach

Write one implementation-ready architecture specification selecting a **shared narrow canonical serialization boundary with artifact-specific encoders**.

Reuse existing `render_toml` semantics and exact-byte hashing conventions rather than introduce a generic serialization framework or typed model hierarchy. Shared primitives define byte encoding, newline, scalar/map serialization, path conversion, and digest timing. Artifact-specific contracts define field order, optional/default normalization, and whether each collection is sorted or order-preserving.

Specification will classify artifacts into:

1. **Canonical deterministic content** — KAPISCH-authored machine-readable snapshots and replaceable derived views; same canonical logical input must serialize identically.
2. **Intentionally variable durable/runtime content** — unique IDs, revisions, exact returned evidence, dates, observations, and metrics; fixed logical records still use canonical serialization where applicable, but repeated real operations need not produce equal values.
3. **Ephemeral transaction state** — locks, journals, backups, staging files, and random temporary paths; names/content may vary and must never leak into canonical final artifacts.

Compatibility policy:

- reading remains tolerant of semantically valid current-version TOML formatting;
- new writes and real semantic mutations use canonical bytes;
- no rewrite occurs solely for formatting;
- replaceable derived views may be regenerated explicitly;
- user-modified managed profiles are never reformatted or replaced without existing ownership/no-drift authorization;
- profile-state schema 1, journal schema 3, and durable v1–v4 schemas remain unchanged;
- pre-2.0 managed-profile migration stays removed;
- exact-byte durable evidence and legacy-copy behavior remain exact-byte contracts;
- shipped implementation would require a backward-compatible minor release under `CONTRIBUTING.md`, while this design-only document requires no version bump.

Canonical rules to specify include:

- UTF-8 without BOM; LF; exactly one final LF for canonical KAPISCH text/TOML unless an existing exact contract requires no trailing LF;
- no Unicode normalization; exact scalar sequence is semantic; unpaired surrogates reject;
- quoted TOML keys/basic strings, deterministic escapes, lowercase booleans, decimal integers, finite floats only, artifact schema order followed by Unicode code-point ordering for extension/unknown-allowed maps;
- required current-version fields emitted; absent optional/empty extension maps omitted; no implicit null; schema-required `"unavailable"` retained;
- canonical bytes hashed after serialization; external evidence, Git output, legacy copies, and pre-existing exact-byte artifacts hashed as persisted without normalization;
- durable internal/repository paths emitted root-relative in POSIX form; absolute/drive/UNC/escaping paths rejected from canonical durable fields;
- native absolute paths retained only where semantically required by machine-local profile ownership and transaction recovery;
- nodes ordered by `(sequence, id)`; dependencies and state membership sorted uniquely; route steps ordered by `(sequence, id)`; content-neutral findings sorted by severity rank then ID; attempts, escalations, verification commands/evidence, explicit context references, batch members, and returned evidence preserve semantic/event order.

## Files to modify

Execution after approval modifies only:

- `docs/superpowers/specs/2026-09-07-deterministic-generated-artifacts-design.md`

This planning file exists only to support Plannotator approval. No scripts, tests, schemas, fixtures, runtime code, package metadata, CI, or release files will change.

## Reuse

Specification will ground recommendations in existing boundaries:

- `plugins/kapisch/kapisch_validation/canonical_toml.py` — current deterministic TOML scalar/map rendering.
- `plugins/kapisch/kapisch_validation/artifact_io.py` — binary-safe regular-file reads and explicit UTF-8 validation.
- `plugins/kapisch/kapisch_validation/controller_view.py` — derived view construction, exact manifest digest, semantic state digest, and projection comparison.
- `plugins/kapisch/scripts/render_controller_view.py` — atomic random temporary name with deterministic published bytes and rollback.
- `plugins/kapisch/scripts/setup_profile.py` — profile newline normalization, fixed-order state records, exact ownership/drift bindings, schema-3 recovery, and random ephemeral recovery paths.
- `plugins/kapisch/scripts/migrate_controller_view_v4.py` — explicit staged canonical v4 conversion.
- `plugins/kapisch/scripts/migrate_legacy_run.py` — explicit byte-preserving legacy compatibility boundary.
- `plugins/kapisch/kapisch_validation/helpers.py` and validators — existing sorted-unique versus order-preserving field evidence.
- `docs/superpowers/specs/2026-09-06-kapisch-2-legacy-compatibility-design.md` — non-migration, ownership, drift, and fail-closed decisions.
- `docs/superpowers/specs/2026-08-31-parent-token-usage-design.md` — authoritative durable state, immutable outcomes, and replaceable derived-view taxonomy.
- `plugins/kapisch/CONTRIBUTING.md` — standard-library, exact-byte, Windows, and semantic-version policy.

## Steps

- [ ] Create target specification with status, scope, baseline revision, problem statement, and explicit non-implementation status.
- [ ] Define semantic, serialization, cross-platform, regeneration, and relocation determinism independently.
- [ ] Add complete artifact inventory table covering profiles, profile records, journal/prepare/recovery artifacts, durable manifests/state, task and review handoffs, reviewer invocation envelopes, delegation route/context/evidence, knowledge ledger, stage outcomes, controller views, metrics, benchmark JSONL, migrations, portable copies, diagnostics, and fixtures.
- [ ] For each artifact record writer/source, readers, retention class, schema/version, nondeterministic inputs, required byte guarantee, reason, and compatibility effect.
- [ ] Add consolidated current nondeterminism analysis: iteration/enumeration, path roots, newlines, exact-byte evidence, IDs, revisions, dates, runtime observations, temporary names, and ambient environment.
- [ ] Compare local normalization, shared narrow serialization, and canonical intermediate-model approaches across correctness, blast radius, compatibility, auditability, drift risk, tests, complexity, and maintenance.
- [ ] Recommend shared narrow boundary and define ownership between shared byte primitives and artifact-specific encoders.
- [ ] Specify exact UTF-8, BOM, newline, TOML scalar/key/map, optional/default, ordering, path, digest, timestamp, identifier, and temporary-file invariants.
- [ ] Define ownership/drift/rewrite rules for KAPISCH-owned output, current recognized state, user drift, compatibility input, migration, and explicit derived regeneration.
- [ ] State schema/version and release implications without reopening profile or durable-run compatibility.
- [ ] Define fail-closed behavior for unsupported values, path ambiguity, noncanonical but valid current input, malformed state, digest mismatch, and failed publication.
- [ ] Define Linux/Windows requirements, including native path containment followed by POSIX relative serialization and environment independence.
- [ ] Add behavioral acceptance matrix for repeated generation, unordered-input shuffle, semantic-order changes, Linux/Windows parity, LF/CRLF perturbation, relocation, locale/timezone/PYTHONHASHSEED changes, derived regeneration, digest stability, user drift, current-state compatibility, and interrupted transaction leakage.
- [ ] Restrict goldens to a few public byte contracts; prefer end-to-end writer/renderer behavior over helper-self-comparison tests.
- [ ] Add rollout strategy, explicit non-goals, closed decisions, and consciously deferred follow-ups. Leave no TBD/TODO.
- [ ] Self-review against accidental migration, durable-version changes, user-file rewrites, vague normalization, contradictory digest rules, helper-only tests, and scope expansion.

## Verification

Document-only verification after writing:

1. Confirm target spec contains all 20 requested sections or clear equivalents.
2. Search target for `TBD`, `TODO`, `FIXME`, placeholders, unresolved alternatives, and contradictory requirement language.
3. Check inventory against every observed writer and every artifact path named by normative contracts.
4. Check each canonical collection has an explicit sort key or explicit order-preservation rule.
5. Check every digest states whether it hashes canonicalized bytes, exact persisted bytes, semantic JSON, or raw Git output.
6. Check every path category states root, separator, containment, and relocation behavior.
7. Check compatibility text explicitly preserves profile-state schema 1, journal schema 3, durable v1–v4, exact-byte evidence, legacy byte-copy migration, current recovery, and user drift.
8. Check acceptance tests exercise public writers/renderers and artifact behavior, not only private helpers.
9. Run `git diff --check`.
10. Confirm Git diff contains only target spec plus this Plannotator plan file and pre-existing untracked planning file; confirm no production/runtime files changed.
