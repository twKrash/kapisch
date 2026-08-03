# Compatibility, migration, and rollback

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

## Source-application dogfood

During stabilization, a consuming source application configures
`twKrash/kapisch` as the `kapisch-local` Git-backed marketplace, installs its
single `kapisch` entry, and invokes `$kapisch`; it must not copy `skills/`,
`roles/`, `agents/`, `kapisch_validation/`, or `scripts/` into its repository.
Its local run evidence belongs under its own ignored `.kapisch/`.

Dogfood sequence:

1. Before claiming Codex-installation acceptance, run
   `codex plugin marketplace add twKrash/kapisch --ref main` in a clean Codex
   environment, then install `kapisch@kapisch-local` and verify `$kapisch` is
   discoverable without profiles.
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
