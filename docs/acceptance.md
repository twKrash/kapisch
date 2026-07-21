# Standalone extraction acceptance

Run the complete acceptance command from the plugin root:

```text
python scripts/test_clean_install.py
```

It copies the plugin into a clean temporary location, validates the Codex plugin
layout, confirms the primary `skills/kapisch/SKILL.md`, and runs the bundled
tests without an application-repository import or existing profile.

The test suite also covers:

| Requirement | Coverage |
| --- | --- |
| Routing and graph-free/durable contracts | `test_manifest.py`, `test_transitions.py`, contract references |
| Resume and lifecycle | `test_cli.py`, `test_transitions.py`, `test_hardening.py` |
| Reviewer invocation and final readiness | `test_review_evidence.py`, `test_hardening.py` |
| Migration and no-new-legacy-write | `test_extraction_acceptance.py` |
| User-scoped profile identity, revision, and drift | `test_extraction_acceptance.py` |
| Read-only deterministic validator | `test_cli.py`, `test_hardening.py` |

`python -m unittest discover -s tests/kapisch_validation` is the focused suite
when a clean installation copy is not required.
