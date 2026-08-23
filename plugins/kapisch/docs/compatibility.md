# Compatibility, migration, and rollback

## Compatibility status

Legacy migration and the `default`/`foundry` presentation themes are
implemented, reviewed, and frozen supported compatibility surfaces. They are
not scheduled for removal; a separate product decision is required before that
changes. Their presence alone does not establish runtime acceptance for a Codex
surface.

## Platform status

- Windows 11 with Codex Desktop and WSL2 completed the 1.0.1 release-baseline
  flow. Keep Codex homes and repositories in the WSL Linux filesystem; see
  [acceptance-windows-v1.0.1.md](acceptance-windows-v1.0.1.md).
- Native Windows Python 3.11 passes profile setup and portable-package tests.
  Live no-WSL marketplace and plugin support is not claimed until every live
  step is observed successfully.
- The immutable Linux 1.0.0 evidence remains historical and unchanged in
  [acceptance-runtime.md](acceptance-runtime.md).

## Validator command compatibility

`kapisch-validate --task-dir PATH` is the primary validator interface after
installing the `kapisch-validation` Python package. It discovers the bundled
contracts without relying on the current working directory. The source-tree
`scripts/validate_kapisch.py` wrapper remains supported and delegates to the
same entry point; callers may remove their old `--contract-dir
<plugin-root>/skills/kapisch` argument. An explicit `--contract-dir PATH`
override remains supported for expert and compatibility use.

## Compatibility version 1

Only `.planning/task-workflow/<task-id>/` is a supported legacy input namespace.
It is read-only. `scripts/migrate_legacy_run.py` copies that directory byte for
byte to `.kapisch/runs/<task-id>/` in a temporary staging directory, validates
the staged canonical tree, and atomically publishes it only on success. The
legacy source is never changed and its evidence is never combined with a
canonical run. Legacy non-TOML knowledge is therefore readable only as legacy
input; newly created machine-readable knowledge is `knowledge/records.toml`.

Migration requires the human-supplied `--approve` flag. It refuses a preexisting
destination. A failed validation leaves no destination and reports the validator
findings. Migration is intentionally outside the read-only validator.

### Migration provenance and trust boundary

Validator acceptance of a terminal legacy reviewer-profile envelope establishes
structural compatibility only; it does not prove that the evidence originated in
the supported legacy namespace or passed through the migration command. Only a
controller-observed, human-approved `migrate_legacy_run.py` copy from
`.planning/task-workflow/<task-id>/`, with source and destination bytes compared
and the source retained through acceptance, establishes operational migration
provenance. Digests detect inconsistent bytes, not authorship.

If the controller cannot establish that supported origin, it must not treat the
legacy profile path as migrated evidence. It blocks reuse and requires a fresh
invocation using `.codex/agents/kapisch-reviewer.toml`. Every newly created
invocation uses that canonical path; accepting a structurally compatible legacy
envelope never authorizes creating one.

## Manifest version 3

Manifest parsing remains a strict closed schema. Version-1 and version-2
parsing, defaults, fixtures, and migration behavior are preserved without
rewriting. Version-3-only fields are rejected on version-1 and version-2
manifests rather than silently adopted:

- `policies.ecosystem_routing` (`"auto"|"off"`) is required only on version-3
  manifests; on older versions it fails with `TWV-SCHEMA-UNSUPPORTED-V3-FIELD`.
- `nodes[].delegation_ids` is version-3-only; on older versions it fails with
  `TWV-SCHEMA-UNSUPPORTED-V3-FIELD`.

Reading an old manifest never creates a route record or delegation fields;
`.kapisch/runs/<task-id>/delegations/` exists only when a delegation actually
occurred. The legacy migration described under Compatibility version 1 is
unchanged: explicit (`--approve`), byte-preserving, source-retaining, and free
of new legacy writes; it neither reads nor writes delegation records.

Delegation records are validated only during version-3 durable validation,
which automatically validates the route record and every graph reference when
a route exists or `delegation_ids` are present. Version-1 and version-2 durable
validation neither reads nor requires delegation records.

## Source-application dogfood

During stabilization, a consuming source application configures
`twKrash/kapisch` as the `kapisch-local` Git-backed marketplace, installs its
single `kapisch` entry, and invokes `$kapisch`; it must not copy `skills/`,
`roles/`, `agents/`, `kapisch_validation/`, or `scripts/` into its repository.
Its local run evidence belongs under its own ignored `.kapisch/`.

Dogfood sequence:

1. For release 1.0.1, run
   `codex plugin marketplace add twKrash/kapisch --ref v1.0.1` in a clean Codex
   environment after the immutable tag is published. Install
   `kapisch@kapisch-local`, start a fresh session, and verify `$kapisch` from the
   installed cache. Record the exact release SHA and tag in
   [`acceptance-windows-v1.0.1.md`](acceptance-windows-v1.0.1.md); never use
   mutable `main` as a release reference. Historical 1.0.0 Unix evidence stays
   in [`acceptance-runtime.md`](acceptance-runtime.md).
2. Run graph-free advisory work without profiles; do not claim approval.
3. Explicitly install `kapisch-reviewer` with `setup_profile.py`, then record a
   fresh canonical reviewer invocation before an approving review.
4. Copy a legacy run only with `migrate_legacy_run.py --approve`; retain its
   source until a human accepts the validated destination.
5. Remove any compatibility copy after the consumer uses the installed plugin
   for one accepted task. No consumer-maintained fork is permitted thereafter.

Adding the marketplace only configures a local Git-backed catalog snapshot. Its
`AVAILABLE` policy does not install or enable KAPISCH automatically. Installation
is a later explicit user action. This flow neither submits to nor depends on the
OpenAI public Plugin Directory.

## Removal boundary and rollback

Remove compatibility version 1 only in a major release after all supported
consumers have either migrated their retained runs or accepted that old runs
cannot resume. Before removal, publish the final compatible release and keep it
available for rollback.

Profile rollback is deliberately non-destructive: inspect the recorded
`installed_profile` and digests in `.kapisch/local-state/profiles/<role>.toml`,
then a human restores their prior user-owned profile from their backup or removes
only the profile they explicitly chose to install. KAPISCH never deletes or
renames it. Removing a profile makes review advisory until a reviewer profile is
explicitly installed again.
