# Standalone extraction acceptance status

| Surface | Status |
| --- | --- |
| Standalone source extraction and portable-package isolation | implemented and reviewed |
| Git-backed local marketplace catalog and plugin-source resolution | implemented and reviewed |
| `codex plugin marketplace add twKrash/kapisch`, installation, fresh-session discovery, reviewer invocation, and `$kapisch` invocation | planned runtime acceptance under [#11](https://github.com/twKrash/kapisch/issues/11) |
| OpenAI public Plugin Directory submission | deferred/archived |

Issue #11 runtime evidence belongs in the checked-in
[`acceptance-runtime.md`](acceptance-runtime.md) accumulator. Its placeholders
must be completed only from the real clean-environment run, including a separate
actual native Windows Codex surface observation.

The repository-level `tests/test_marketplace.py` verifies the implemented closed marketplace
catalog, `AVAILABLE` installation policy, canonical `./plugins/kapisch` source,
plugin identity, and documented GitHub import/install commands. It does not
modify a developer's Codex configuration or claim live installation acceptance.

The portable test below does not install a plugin through Codex. It prevents
source-application imports from being hidden by the development checkout.

Run the complete acceptance command from the plugin root:

```text
python scripts/test_portable_package.py
```

It copies the plugin into a clean temporary location, checks the bundled
manifest and primary `skills/kapisch/SKILL.md`, and runs the bundled tests
without an application-repository import or existing profile.

The test suite also covers:

| Requirement | Coverage |
| --- | --- |
| Git-backed local marketplace metadata and source resolution | repository-level `tests/test_marketplace.py` |
| Routing and version-3 durable contracts | `test_manifest.py`, `test_transitions.py`, contract references |
| Closed policy/node-routing/workflow vocabularies and workflow state/action consistency | `test_vocabulary.py`, `test_transitions.py`, `test_cli.py` |
| Resume, lifecycle, and previous-snapshot history compatibility | `test_cli.py`, `test_transitions.py`, `test_hardening.py` |
| Reviewer invocation and final readiness | `test_review_evidence.py`, `test_hardening.py` |
| Migration and no-new-legacy-write | `test_extraction_acceptance.py` |
| User-scoped profile identity, revision, and drift | `test_extraction_acceptance.py` |
| Project-understanding procedures, role boundaries, handoffs, review policy, and local links | `test_extraction_acceptance.py` |
| Presentation theme vocabulary and semantic firewall | `test_themes.py` |
| Ecosystem routing contract, route schema, read-only execution boundary, and evidence files | `test_delegations.py` |
| Manifest version 3 policy and node fields; v1/v2 rejection | `test_manifest.py` |
| Delegation route gating and v3 auto-validation | `test_delegations.py` |
| Portable version-3 durable validation (with route record) | `scripts/test_portable_package.py` |
| Read-only deterministic validator | `test_cli.py`, `test_hardening.py` |
| Installed `kapisch-validate`, bundled contract discovery, explicit override, and legacy wrapper | `test_console_command.py` |

`test_transitions.py` covers stable task identity, missing/renamed nodes,
immutable graph fields, terminal artifact/assignment/evidence bindings,
rejected graph growth without an amendment protocol, unchanged idempotent resume, and legal
status progression. `test_cli.py` proves that the same compatibility boundary is
enforced when `--previous-task-dir` is supplied.

`python -m unittest discover -s tests/kapisch_validation` is the focused suite
when portable-package isolation is not required.

## Change 5 dogfood observability decision

Policy B was accepted on 2026-07-22. Researcher dogfood may record
`resolved_runtime_profile=unavailable/not exposed` when the collaboration runtime
does not expose profile selection, provided the installed profile identity and
revision are recorded, drift is absent, and the result does not infer selection
from installation. This decision applies only to advisory researcher dogfood. It
does not weaken the configured-reviewer invocation and canonical evidence needed
for independent approval or milestone final readiness.

## Ecosystem-routing acceptance (Change 7)

### Automated coverage

- `tests/kapisch_validation/test_delegations.py` covers the closed route schema
  (unknown fields, allowed enums, step-ID grammar, duplicate IDs and
  sequences), evidence-file integrity (path containment, symlink rejection,
  UTF-8, lowercase SHA-256 digests), acceptance of `repository-read` and
  `external-read`, fail-closed rejection of `external-write` and `destructive`
  even with declared authority, graph parent ownership and unique references, review/final
  read-only delegation, route/manifest identity, and the version-3 durable CLI
  path (including `ecosystem_routing=off` gating and missing-route-with-refs
  rejection).
- `tests/kapisch_validation/test_manifest.py` covers the version-3
  `policies.ecosystem_routing` and `nodes[].delegation_ids` fields and their
  rejection on version-1 and version-2 manifests
  (`TWV-SCHEMA-UNSUPPORTED-V3-FIELD`).
- `scripts/test_portable_package.py` runs one version-3 durable validation
  (with a delegation route record) from the isolated package copy.

### Manual clean-environment runtime acceptance (planned under [#11](https://github.com/twKrash/kapisch/issues/11))

Phase 8 of the Change 7 execution plan is recorded as pending manual
acceptance; it has not been executed in this environment. Acceptance checklist:

1. Explicitly invoke an installed instruction-only skill through KAPISCH.
2. Automatically select a plugin-bundled read-only skill.
3. Use an external-read connector with only the focused context.
4. Prepare an external-write preview and verify the delegated route is rejected
   even when the exact target, payload, and explicit authority are recorded.
5. Name an unavailable plugin and verify fail-closed behavior.
6. Run on a surface without plugin support and verify disclosed native
   fallback or a precise blocker.
7. Install a plugin and verify its capability only in a fresh session when the
   runtime requires that refresh.
8. Verify resume cannot classify an unsupported interrupted delegated
   external-write step as safely retryable.
9. Use a specialist review capability and verify that it remains advisory
   until the configured KAPISCH reviewer produces canonical evidence.
10. Verify that KAPISCH never installs, authenticates, commits, pushes,
    publishes, sends, or performs destructive work without the corresponding
    explicit authority.

Each scenario records exposed capability identifiers, surface, plugin/skill
availability, context and evidence paths, human gates, exact checks, and
outcomes. Unexposed runtime receipts are recorded as `unavailable`; they are
never inferred.

Structural routing validation and read-only delegated execution are implemented;
external-effect reconciliation is not. Lifting the write restriction requires a
versioned intent/start/result/completion lifecycle, stable provider operation
identifiers, read-only reconciliation of ambiguous outcomes, documented provider
idempotency support, and crash/interruption acceptance proving no blind retry.
No criterion establishes exactly-once delivery.

### Approved deviation (2026-08-04)

The user approved implementing Change 7 before clean Codex installation, plugin
discovery, and `$kapisch` invocation acceptance complete. Clean-install and
marketplace import/installation acceptance remain separate manual release
gates; they are not coding gates for this change. The Phase 8 scenarios above
are therefore recorded as pending manual acceptance evidence, not executed in
this environment.

### Supported surface matrix

| Surface | Capability exposure | Verification |
| --- | --- | --- |
| Codex desktop and CLI | can exercise plugin-bundled skills and tools | planned runtime acceptance under [#11](https://github.com/twKrash/kapisch/issues/11) |
| Surface without plugin support | may expose local skills and must degrade safely (disclosed native fallback or a precise blocker) | planned runtime acceptance under [#11](https://github.com/twKrash/kapisch/issues/11) |
