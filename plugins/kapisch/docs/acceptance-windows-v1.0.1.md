# Windows acceptance record — 1.0.1

Status: **released and accepted at the exact release SHA**. This record contains
no credentials, authentication files, or secret values.

## Revisions

- Release: `1.0.1`; intended immutable tag: `v1.0.1`.
- Merged PR #20 baseline:
  `0e19cc4c9f25ae9cc502504a1d77eab1bcea70fe`.
- `RELEASE_SHA`:
  `992c40c41c61a196dce9e52237a17528db949307`.
- Exact-release-SHA CI:
  [run 32734673050](https://github.com/twKrash/kapisch/actions/runs/32734673050),
  completed successfully for Linux and Windows.
- PR #22 was approved at the exact `RELEASE_SHA` before publication.
- Annotated tag object: `1fe5233c5dbe49f678740130e1b8e421cc725c6f`.
- Remote `v1.0.1^{}`:
  `992c40c41c61a196dce9e52237a17528db949307`.
- Existing remote `v1.0.0^{}` remained
  `d186b90592f65f9861c680d852ee05723f982903`.

No runtime defect was reproduced at either the baseline or release SHA. Release
1.0.1 therefore changes release metadata, tests, and documentation only; it
adds no dependency, service, platform fork, or production-code branch.

## Environment

| Component | Observed value |
| --- | --- |
| Windows | Windows 11 Pro, 64-bit, `10.0.26200.8973` |
| Codex Desktop | `26.818.5229.0` |
| Codex CLI | `0.149.0-alpha.4.1` |
| WSL | `2.7.3.0`, kernel `6.6.114.1-1`, WSL2 |
| Distribution | Ubuntu 26.04 LTS, x86_64 |
| WSL Python | 3.14.4 |
| Native Windows Python | CPython 3.11.15 via uv 0.11.15 |

`CODEX_HOME`, the installed marketplace, and each consumer repository were
kept in the WSL Linux filesystem, not under `/mnt/c`.

## Marketplace and plugin proof

A new authenticated home was created with normal `codex login`; credentials
were not copied. The baseline marketplace was added by full SHA:

```text
codex plugin marketplace add twKrash/kapisch --ref 0e19cc4c9f25ae9cc502504a1d77eab1bcea70fe --json
codex plugin add kapisch@kapisch-local
codex plugin list --available --json
```

The cached marketplace repository resolved to the same full SHA. The sole
plugin was `kapisch@kapisch-local`, version 1.0.0 at this pre-bump baseline,
installed and enabled from the marketplace cache rather than the development
checkout.

The post-approval rerun used an entirely new authenticated home, marketplace
cache, and unrelated consumer. It replaced the baseline SHA above with the full
`RELEASE_SHA`:

```text
codex plugin marketplace add twKrash/kapisch --ref 992c40c41c61a196dce9e52237a17528db949307 --json
codex plugin add kapisch@kapisch-local
codex plugin list --available --json
```

The new cache resolved exactly to `RELEASE_SHA`; the installed and enabled
plugin reported version 1.0.1.

## Profile proof

From the marketplace-cached plugin:

```text
python <installed-plugin>/scripts/setup_profile.py --all --project-dir <consumer> --install
python <installed-plugin>/scripts/setup_profile.py --all --project-dir <consumer>
```

At both the baseline and the entirely new release-SHA consumer, all six
identities matched their templates with `drift=none` and
`template_drift=none`:

| Profile | SHA-256 |
| --- | --- |
| `kapisch-architect` | `c85615400d67a80f6538031f7aad2e5424140f969b3484fb490006766ed57815` |
| `kapisch-implementer-lite` | `e2f0834c539c6ecf47edd7ccdaefbb2c57043c626c09258b97cce3cbfd52125f` |
| `kapisch-implementer` | `4f076716ac1ee26c0865082182cc66fef10f69c78b1200d9d4e99a10127305a5` |
| `kapisch-mechanic` | `2efc547670bf175555c102ff19c8539b706aad5d078cb37e073d68003baf08a6` |
| `kapisch-researcher` | `609913b8db5de874abfcd585a78d602bc22abd50df4a6a7cf600134bc00e88bf` |
| `kapisch-reviewer` | `6d01210c00a61058bc460bd42232956d1279f3a3e76ebb8e7d4ac9ea7fa076b7` |

The profiles were committed as consumer baseline configuration before the live
task, so they did not pollute task working-tree evidence.

## Durable task

The baseline accepted run used a fresh persistent session after an ephemeral
parent hit a missing-thread lookup during named child dispatch in this Codex
alpha build:

```text
codex exec --json --sandbox workspace-write -C <consumer> \
  'Use $kapisch with DURABLE end-to-end execution to add a short Installation section to README.md. Do not commit, push, authenticate elsewhere, or perform external writes. Complete the durable workflow, including implementation, independent review, final synthesis, and validation.'
```

- Task ID: `readme-installation`.
- Selected implementation role: `implementer`.
- Consumer baseline revision:
  `5794842ae74a1a3917a70fa7b7fd4d5a26cb9ab5`.
- Source delta: only `README.md`, eight added lines, no commit or external write.
- Integrated reviewer decision: `approve`, no findings.
- Separate final-readiness decision: `ready`, no issues.
- Final workflow state: `complete`.
- Artifacts: plan, version-3 execution graph, state, T01/R01/F01 briefs and
  contexts, implementation report, canonical review/final invocation envelopes,
  and review/final results under `.kapisch/runs/readme-installation/`.

Two earlier isolated attempts were retained as diagnostic evidence: one exposed
untracked consumer setup contaminating canonical Git state, and one used
`--ephemeral` for a parent that needed named child dispatch. Neither reproduced
a KAPISCH Windows path or byte-handling defect.

The frozen release-SHA rerun then repeated the flow with no reused home, cache,
consumer, session, or durable artifact:

- Consumer baseline:
  `394a4a5de2143497dd8ddaf7e3230c59d3137bd6`.
- Source delta: only `README.md`, four added lines, with no commit or external
  write.
- Integrated reviewer: `approve`, no P0-P3 findings.
- Separate final readiness: `ready`, no blocking findings.
- Final workflow state: `complete`; T01, R01, and F01 were complete.
- Durable artifact-tree digest:
  `4c177c10b67f4f3d823665fbe4ef6bfcea4df01f819bdee21be41721fd1394bc`.

## Separate read-only reviewer

The required fresh parent was run with the explicit read-only sandbox:

```text
codex exec --json --ephemeral --sandbox read-only -C <consumer> \
  'Explicitly invoke the configured kapisch-reviewer profile as a named independent reviewer against task readme-installation and the current README.md working-tree delta. The parent and reviewer must remain read-only. Return an explicit decision and findings.'
```

The named `kapisch-reviewer` resolved and returned advisory decision `approve`
with no P0-P3 findings. Pre/post Git output, the README diff, and every existing
durable-artifact SHA-256 were identical. Because the parent was read-only, it
could not create a new canonical invocation envelope; this separate decision is
correctly advisory. The durable task's own canonical review and final evidence
remain the approving records.

The release-SHA run repeated the separate fresh parent check. A first sandboxed
launch could not reach the Codex service and was stopped after network retries;
the identical network-enabled command then exited 0, resolved the configured
reviewer as `/root/readme_installation_review`, and returned advisory
`approve` with no P0-P3 findings. Before and after the successful read-only
run, the hashes were identical:

- Git status:
  `57c31c6f45d894eed17e32ccb813409085dda4093a3646b2713203a0a7dd49a3`.
- Binary working-tree diff:
  `6fc605802a239f243c1a19a78826966273dcecf977513d4631a8ad99c9ce0387`.
- Durable artifact tree:
  `4c177c10b67f4f3d823665fbe4ef6bfcea4df01f819bdee21be41721fd1394bc`.
- Consumer README:
  `0b873cb64f1499844fac3067523879b74995476724bc3718e7f39cc721c01485`.

## Public validator

The validation package was installed into an isolated environment directly from
the marketplace-cached plugin. No `--contract-dir` override was used:

```text
kapisch-validate --task-dir <consumer>/.kapisch/runs/readme-installation --format json
[]
```

Exit code: `0`. Output: exactly `[]` plus the terminating newline.
The same result was observed after installing version 1.0.1 directly from the
new release-SHA marketplace cache into a new isolated Python environment.

## Automated gates

At the exact baseline SHA:

- Linux root suite: 7 tests passed.
- Linux validator suite: 245 tests run; suite passed.
- Linux portable package: 245 tests run; suite passed;
  `portable-package=passed`.
- Native Windows profile suite: 16 tests passed on CPython 3.11.15.
- Native Windows portable package: 245 tests run; five capability-based
  filesystem skips; suite passed; `portable-package=passed`.
- Validator wrapper/help smoke test passed.

After the 1.0.1 version, test, and documentation edits, including the
documentation-contract regression added during PR review, the candidate
repeated the same gates: Linux root 8/8; Linux validator and portable suites
each ran 246 tests and passed; native Windows profiles passed 16/16; and native
Windows portable ran 246 tests with the same five capability-based skips and
passed.

Immediately before tagging the frozen `RELEASE_SHA`, the Linux gates were
repeated: root 8/8, validator 246/246, portable 246/246 with
`portable-package=passed`, wrapper/help smoke, and `git diff --check`. The
wheel-install tests initially stopped because sandboxed build isolation could
not download the declared `setuptools>=70.4` backend; the identical
network-enabled reruns passed. This was an environment boundary, not a product
failure.

Native Windows commands were run from an isolated NTFS copy, not `/mnt/c` from
inside WSL:

```text
uv run --python 3.11 --no-project -- python -m unittest discover -s tests/kapisch_validation -p test_setup_profile.py
uv run --python 3.11 --no-project -- python scripts/test_portable_package.py
```

## Native no-WSL attempt

The optional PowerShell flow stopped at its first boundary. `Get-Command codex`
returned no native CLI alias. The app package contains a `resources/codex.exe`,
but direct `--version` execution from PowerShell returned `Access is denied`;
the packaged executable is not a supported command alias on this installation.
No marketplace, plugin, profile, or consumer mutation was attempted after that
boundary. Native no-WSL live support is therefore not claimed.
The frozen release-SHA attempt reproduced the same first boundary.

```powershell
Get-Command codex -ErrorAction SilentlyContinue
& 'C:\Program Files\WindowsApps\OpenAI.Codex_26.818.5229.0_x64__2p2nqsd0c76g0\app\resources\codex.exe' --version
```

## Limits

- The native Windows, no-WSL attempt could not start a supported Codex CLI, as
  recorded above. The Python gates pass, but live support is not claimed.
- The full durable task used a fresh persistent parent; `--ephemeral` parent
  lookup was unreliable for named child dispatch in Codex CLI
  `0.149.0-alpha.4.1`. The separate required ephemeral read-only reviewer did
  complete successfully.
- Windows support is verified for Codex Desktop with WSL2 using the WSL Linux
  filesystem. Native no-WSL live support is not claimed.
- The post-tag follow-up changes acceptance evidence only. The tagged runtime,
  versions, installation commands, schemas, profiles, and dependencies are
  unchanged.
- OpenAI public Plugin Directory publication and delegated external-write or
  destructive execution remain out of scope.
