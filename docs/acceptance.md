# Standalone extraction acceptance status

| Surface | Status |
| --- | --- |
| Standalone source extraction and portable-package isolation | completed |
| Codex installation, plugin discovery, and `$kapisch` invocation | pending manual clean-environment acceptance |
| Marketplace distribution | pending |

The portable test below does not install a plugin through Codex or exercise a
marketplace. It prevents source-application imports from being hidden by the
development checkout.

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
| Routing and graph-free/durable contracts | `test_manifest.py`, `test_transitions.py`, contract references |
| Resume and lifecycle | `test_cli.py`, `test_transitions.py`, `test_hardening.py` |
| Reviewer invocation and final readiness | `test_review_evidence.py`, `test_hardening.py` |
| Migration and no-new-legacy-write | `test_extraction_acceptance.py` |
| User-scoped profile identity, revision, and drift | `test_extraction_acceptance.py` |
| Project-understanding procedures, role boundaries, handoffs, review policy, and local links | `test_extraction_acceptance.py` |
| Read-only deterministic validator | `test_cli.py`, `test_hardening.py` |

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
