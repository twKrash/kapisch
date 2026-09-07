# Compatibility, migration, and rollback

## Compatibility status

Legacy migration and the `default`/`foundry` presentation themes remain frozen
supported compatibility surfaces. Their presence alone does not establish runtime
acceptance for a Codex surface.

## Platform status

- Windows 11 with Codex Desktop and WSL2 completed the historical 1.0.1
  release-baseline flow.
- Native Windows automated CI is required for 2.0.0; live no-WSL marketplace and
  plugin support is not claimed until every live step is observed successfully.
- The immutable Linux 1.0.0 evidence remains historical and unchanged in
  [acceptance-runtime.md](acceptance-runtime.md).

## Validator command compatibility

`kapisch-validate --task-dir PATH` is the primary validator interface after
installing the `kapisch-validation` Python package. It discovers bundled
contracts without relying on the current working directory. The source-tree
`scripts/validate_kapisch.py` wrapper and explicit expert `--contract-dir PATH`
override remain supported.

## Agent profile-set compatibility

Release 2.0.0 established an intentional local-profile compatibility boundary.
The runtime is semver-independent: current local state uses
`profile_state_version = 1` and the switch journal uses schema 3; neither number
is the plugin version. `balanced`, `quality`, and `budget` remain installer-time
runtime configurations for the same six identities and do not change durable
model tiers, approval authority, risk classification, or independent review.

Current records bind the selected profile set, template filename, identity,
installed path, and digests. Structural diagnosis identifies old records and
journal schemas 1–2 as legacy, but diagnosis is not ownership: unsupported
legacy state is rejected without mutation. KAPISCH does not retain historical
bytes or digest allowlists to claim ownership, and provides no automatic
migration or recovery for that state.

Ordinary install remains non-overwriting. Same-set and routing changes require
`--install --replace-managed`; identity, catalog, state, installed digest, and
no-drift checks must all pass. Current schema-3 recovery can restore or finish
an explicitly authorized interrupted replacement while preserving later user
edits. User-modified, unrelated, missing, or legacy profiles are never switched
or removed by KAPISCH.

## Legacy profile cleanup

Stop concurrent profile setup processes before inspection or cleanup. Run the
2.x inspector for the scope being reset and record every path it lists:

```text
# Project scope
python scripts/setup_profile.py --all --project-dir <consumer-repository>

# User scope
python scripts/setup_profile.py --all --scope user --user-dir <user-home>
```

The list can contain profile files, companion state records, the fixed
`profile-switch.toml` journal, or the fixed `.profile-switch.prepare.tmp`
preparation file. Inspector can also return `legacy_switch_artifact=<exact path>`. 
Remove only the exact paths listed by setup. Do not infer
ownership from similar names, follow paths embedded in a legacy journal, or add
nearby files to the cleanup list.

Exact .kapisch-switch.bak/.tmp sibling paths can be reported as possible
residue from an interrupted pre-2.0 replacement.

Their names are not proof of ownership. Back them up and inspect them.
Remove them only if they belong to the old KAPISCH installation.

WSL users follow the POSIX procedure below and use Linux paths. For each listed
path, choose a distinct backup path so profile and state files with the same
basename cannot overwrite one another:

```bash
mkdir -p "$HOME/kapisch-profile-backup"
printf 'Paste one exact path listed by setup: '
IFS= read -r LEGACY_PATH
printf 'Enter a distinct backup path under $HOME/kapisch-profile-backup: '
IFS= read -r BACKUP_PATH
cp -- "$LEGACY_PATH" "$BACKUP_PATH"
printf 'Inspect the backup, then press Enter to remove the listed original.'
IFS= read -r _confirmation
rm -- "$LEGACY_PATH"
```

On native Windows PowerShell, repeat this equivalent sequence for each listed
path:

```powershell
New-Item -ItemType Directory -Force "$HOME\kapisch-profile-backup"
$LegacyPath = Read-Host "Paste one exact path listed by setup"
$BackupPath = Read-Host "Enter a distinct backup path under $HOME\kapisch-profile-backup"
Copy-Item -LiteralPath $LegacyPath -Destination $BackupPath
Read-Host "Inspect the backup, then press Enter to remove the listed original"
Remove-Item -LiteralPath $LegacyPath
```

Inspect every backup and confirm that it belongs to the installation being
reset before removing its original. Never delete `.kapisch` wholesale: durable
run evidence can coexist beneath it.

Optionally remove now-empty KAPISCH setup directories such as the selected
root's `.kapisch/local-state/profiles/` and
`.kapisch/local-state/`, but only with a non-recursive empty-directory removal.
Do not remove the shared `.codex/agents/` directory.

After all listed files are removed, rerun the applicable project or user
inspection command above. It must report a fresh `not-installed` state before
reinstallation. Then use the matching ordinary install command:

```text
# Project reinstall
python scripts/setup_profile.py --all --project-dir <consumer-repository> --install

# User reinstall
python scripts/setup_profile.py --all --scope user --user-dir <user-home> --install
```

Run the matching inspection command once more after reinstall:

- Verify every installed profile has the expected `kapisch-<role>` identity.
- Verify inspection reports no drift (`drift=none`).
- Confirm `update_required=false`, proving immediate inspection introduces no
  state drift.

Plugin uninstall remains a separate operation and does not prove ownership of,
or remove, optional profile files.

## Durable-run legacy migration

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
occurred. The legacy migration described under Durable-run legacy migration is
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

Remove durable-run compatibility version 1 only in a major release after all supported
consumers have either migrated their retained runs or accepted that old runs
cannot resume. Before removal, publish the final compatible release and keep it
available for rollback.

Profile rollback is deliberately managed and non-destructive: inspect the recorded
`installed_profile` and digests in `.kapisch/local-state/profiles/<role>.toml`,
then explicitly switch a verified KAPISCH-managed profile back to its prior set,
or have a human restore their user-owned profile from their own backup. KAPISCH
never deletes an installed profile. Removing a profile makes review advisory
until a reviewer profile is explicitly installed again.
