# KAPISCH 2.0 Legacy Profile Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship KAPISCH 2.0.0 with a release-independent current profile-state format, safe current updates, and non-mutating rejection of legacy profile/setup state.

**Architecture:** Keep `setup_profile.py` as the single installer and transaction owner. Add explicit current-state schema fields, separate ownership from desired-output updates, normalize generated profile bytes, and replace old recovery compatibility with structural legacy diagnostics. Preserve the existing lock and atomic transaction model for current state only.

**Tech Stack:** Python 3.11 standard library (`argparse`, `hashlib`, `pathlib`, `tomllib`, `unittest`), TOML profile/state files, GitHub Actions on Ubuntu and native Windows.

**Spec:** `docs/superpowers/specs/2026-09-06-kapisch-2-legacy-compatibility-design.md`

**Execution prerequisite:** The approved spec and this plan must already be
tracked in Git, and `git status --short` must be empty before Task 1 starts. The
five task commits below intentionally cover implementation and release files,
not these already-committed planning documents.

## Global Constraints

- Target plugin release is exactly `2.0.0` in `plugins/kapisch/.codex-plugin/plugin.json` and `plugins/kapisch/pyproject.toml`.
- Current profile-state schema is exactly `profile_state_version = 1`; it is independent of plugin semantic versions.
- Current switch-journal schema is exactly version `3`; journal versions 1 and 2 are diagnostics-only legacy state.
- Runtime source and diagnostics must not compare against or print plugin release `2.0`.
- Preserve the six identities: `kapisch-architect`, `kapisch-implementer-lite`, `kapisch-implementer`, `kapisch-mechanic`, `kapisch-researcher`, and `kapisch-reviewer`.
- Preserve `balanced`, `quality`, and `budget` profile-set semantics except when a test deliberately patches routing to prove supported updates.
- Never automatically migrate, recover, rewrite, or delete legacy profile/setup state.
- Never infer ownership from a pathname, filename, or profile identity alone.
- Preserve user drift, symlinks, unreadable files, unrelated profiles, and ambiguous transaction artifacts.
- Keep durable-run manifest/controller-view schemas v1-v4, validator behavior, and migration compatibility unchanged.
- Do not add dependencies or new CI jobs.
- Native Windows profile-setup and portable-package CI remains required; manual native-PowerShell live acceptance is optional.
- `plugins/kapisch/tests/fixtures/legacy-1.0.1/`, its digest allowlist, its `.gitattributes` rule, and `docs/acceptance-windows-v1.2.2.md` must remain absent.
- Do not modify the six agent templates, `.agents/plugins/marketplace.json`, `.github/workflows/quality.yml`, `.gitattributes`, or durable validator/migration implementation.

## File Responsibility Map

### Runtime and focused tests

- Modify `plugins/kapisch/scripts/setup_profile.py`: current state schemas, normalized rendering, ownership/update classification, legacy rejection, and current-only transaction recovery.
- Modify `plugins/kapisch/tests/kapisch_validation/test_setup_profile.py`: TDD coverage for every installer state and removal of old compatibility tests.

### Release policy and documentation

- Modify `tests/test_marketplace.py`: version-generic release provenance and current-documentation assertions.
- Modify `README.md`: immutable `v2.0.0` install command and top-level upgrade warning.
- Modify `plugins/kapisch/README.md`: current setup/update/legacy behavior.
- Modify `plugins/kapisch/docs/compatibility.md`: normative compatibility boundary and manual cleanup.
- Modify `plugins/kapisch/docs/profile-sets.md`: current state/update contract.
- Modify `plugins/kapisch/docs/acceptance.md`: current 2.0.0 candidate status and historical labeling.
- Modify `plugins/kapisch/CONTRIBUTING.md`: policy against incidental legacy migration machinery.
- Modify `plugins/kapisch/CHANGELOG.md`: 2.0.0 breaking-change entry.
- Modify `plugins/kapisch/.codex-plugin/plugin.json`: version `2.0.0`.
- Modify `plugins/kapisch/pyproject.toml`: version `2.0.0`.
- Create `plugins/kapisch/docs/acceptance-windows-v2.0.0.md`: pending release-candidate evidence record.

### Files that must not change

- `.agents/plugins/marketplace.json`
- `.github/workflows/quality.yml`
- `.gitattributes`
- `scripts/check_plugin_version.py`
- `plugins/kapisch/agents/*.toml`
- `plugins/kapisch/kapisch_validation/**`
- durable migration scripts and fixtures

---

### Task 1: Introduce the Current Profile-State Format and Normalized Rendering

**Files:**

- Modify: `plugins/kapisch/scripts/setup_profile.py:15-214,285-482`
- Modify: `plugins/kapisch/tests/kapisch_validation/test_setup_profile.py:17-396,399-629`

**Interfaces:**

- Produces: `CURRENT_PROFILE_STATE_VERSION: int = 1`
- Produces: `CURRENT_SWITCH_JOURNAL_VERSION: int = 3` for Task 4
- Produces: `_normalize_template_bytes(contents: bytes) -> bytes`
- Extends: `_record_text(...) -> str` with current schema and installed routing fields
- Preserves: `_render_profile_bytes(canonical: bytes, *, role: str, profile_set: str) -> bytes`
- Later tasks consume the new record fields `profile_state_version`, `installed_model`, and `installed_model_reasoning_effort`.

- [ ] **Step 1: Add failing normalized-rendering and record-schema tests**

In `SetupProfileSafetyTests`, add:

```python
    def test_lf_and_crlf_templates_render_identically(self) -> None:
        role = "reviewer"
        source = (setup_profile.AGENT_DIR / "kapisch-reviewer.toml").read_bytes()
        lf = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")

        self.assertEqual(
            setup_profile._render_profile_bytes(
                lf, role=role, profile_set="balanced"
            ),
            setup_profile._render_profile_bytes(
                crlf, role=role, profile_set="balanced"
            ),
        )
        self.assertNotIn(
            b"\r\n",
            setup_profile._render_profile_bytes(
                crlf, role=role, profile_set="balanced"
            ),
        )
```

Add an installation-level regression test so rendering alone cannot mask a
hashing-path regression:

```python
    def test_lf_and_crlf_template_installs_have_identical_bytes_and_digests(
        self,
    ) -> None:
        source = (setup_profile.AGENT_DIR / "kapisch-reviewer.toml").read_bytes()
        lf = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        variants = {"lf": lf, "crlf": lf.replace(b"\n", b"\r\n")}
        results: dict[str, tuple[bytes, str, str]] = {}

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, template_bytes in variants.items():
                agent_dir = root / f"{name}-agents"
                agent_dir.mkdir()
                (agent_dir / "kapisch-reviewer.toml").write_bytes(template_bytes)
                project = root / f"{name}-project"
                with mock.patch.object(setup_profile, "AGENT_DIR", agent_dir):
                    self.assertEqual(
                        setup_profile.main(
                            [
                                "--role",
                                "reviewer",
                                "--project-dir",
                                str(project),
                                "--install",
                            ]
                        ),
                        0,
                    )
                state = tomllib.loads(
                    (
                        project
                        / ".kapisch/local-state/profiles/reviewer.toml"
                    ).read_text(encoding="utf-8")
                )
                results[name] = (
                    (
                        project / ".codex/agents/kapisch-reviewer.toml"
                    ).read_bytes(),
                    state["template_sha256"],
                    state["installed_sha256"],
                )

        self.assertEqual(results["lf"], results["crlf"])
```

Existing project/user-scope tests continue to verify native target-path binding;
this test isolates checkout line endings from installed bytes and both digests.

Extend `ProfileSetTests.test_default_install_uses_balanced_and_records_the_set`
with exact assertions for its researcher record, and change its template digest
expectation to hash normalized canonical bytes:

```python
            self.assertEqual(state["profile_state_version"], 1)
            self.assertEqual(state["installed_model"], "gpt-5.6-terra")
            self.assertEqual(
                state["installed_model_reasoning_effort"], "medium"
            )
            self.assertEqual(
                state["template_sha256"],
                hashlib.sha256(
                    setup_profile._normalize_template_bytes(
                        (
                            setup_profile.AGENT_DIR
                            / "kapisch-researcher.toml"
                        ).read_bytes()
                    )
                ).hexdigest(),
            )
```

Also extend
`ProfileSetTests.test_each_profile_set_installs_the_exact_six_role_routing_matrix`.
Inside its existing `for role, (model, effort) in expected.items()` loop, parse
the role's companion state and assert all current routing fields:

```python
                    state = tomllib.loads(
                        (
                            project
                            / f".kapisch/local-state/profiles/{role}.toml"
                        ).read_text(encoding="utf-8")
                    )
                    self.assertEqual(state["profile_state_version"], 1)
                    self.assertEqual(state["profile_set"], profile_set)
                    self.assertEqual(state["installed_model"], model)
                    self.assertEqual(
                        state["installed_model_reasoning_effort"], effort
                    )
```

- [ ] **Step 2: Run the new tests and verify the intended failures**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.SetupProfileSafetyTests.test_lf_and_crlf_templates_render_identically \
  tests.kapisch_validation.test_setup_profile.SetupProfileSafetyTests.test_lf_and_crlf_template_installs_have_identical_bytes_and_digests \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_default_install_uses_balanced_and_records_the_set \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_each_profile_set_installs_the_exact_six_role_routing_matrix \
  -v
```

Expected: FAIL because CRLF is preserved and the three new state fields are
missing.

- [ ] **Step 3: Add schema constants and canonical newline normalization**

Near the profile catalogs in `setup_profile.py`, add:

```python
CURRENT_PROFILE_STATE_VERSION = 1
CURRENT_SWITCH_JOURNAL_VERSION = 3
```

Add this helper immediately before `_parse_profile_bytes`:

```python
def _normalize_template_bytes(contents: bytes) -> bytes:
    try:
        text = contents.decode("utf-8")
    except UnicodeError as exc:
        raise ProfileReadError(str(exc)) from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
```

At the start of `_render_profile_bytes`, normalize before parsing:

```python
def _render_profile_bytes(canonical: bytes, *, role: str, profile_set: str) -> bytes:
    """Render one deterministic runtime profile from the canonical role contract."""
    canonical = _normalize_template_bytes(canonical)
    values = _parse_profile_bytes(canonical)
```

Because `canonical` is normalized, replace the conditional line-ending choice in
both rewritten model fields with an unconditional `"\n"`.

In `_prepare_role`, normalize the one template read before parsing, rendering,
and hashing:

```python
        template_bytes = _normalize_template_bytes(template.read_bytes())
        template_values = _parse_profile_bytes(template_bytes)
        desired_bytes = _render_profile_bytes(
            template_bytes, role=role, profile_set=profile_set
        )
        template_digest = hashlib.sha256(template_bytes).hexdigest()
```

Update `ProfileSetTests._expected_set_bytes` to use the same normalization before
rendering or hashing:

```python
            canonical = setup_profile._normalize_template_bytes(
                template.read_bytes()
            )
```

This keeps runtime validation, expected-byte helpers, and hashing on the same
normalized bytes.

- [ ] **Step 4: Write current schema and resolved routing into every new record**

Update `_record_text` to derive the installed routing and render the integer
schema field unquoted:

```python
def _record_text(
    *,
    template: Path,
    template_digest: str,
    target: Path,
    scope: str,
    role: str,
    profile_set: str,
    installed_digest: str,
) -> str:
    installed_model, installed_effort = PROFILE_SET_ROUTING[profile_set][role]
    fields = (
        ("template", template.name),
        ("template_sha256", template_digest),
        ("installed_profile", target),
        ("scope", scope),
        ("profile_set", profile_set),
        ("profile_identity", f"kapisch-{role}"),
        ("installed_model", installed_model),
        ("installed_model_reasoning_effort", installed_effort),
        ("installed_sha256", installed_digest),
    )
    return (
        f"profile_state_version={CURRENT_PROFILE_STATE_VERSION}\n"
        + "".join(
            f"{name}={toml_basic_string(value)}\n" for name, value in fields
        )
    )
```

Do not store the plugin release version in the record.

- [ ] **Step 5: Run the focused tests and full profile-setup module**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.SetupProfileSafetyTests.test_lf_and_crlf_templates_render_identically \
  tests.kapisch_validation.test_setup_profile.SetupProfileSafetyTests.test_lf_and_crlf_template_installs_have_identical_bytes_and_digests \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_default_install_uses_balanced_and_records_the_set \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_each_profile_set_installs_the_exact_six_role_routing_matrix \
  -v
python -m unittest tests.kapisch_validation.test_setup_profile -v
```

Expected: all focused tests and the full setup module PASS. Do not commit Task 1
with a failing setup test.

- [ ] **Step 6: Commit the current record format**

```bash
git add \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py
git commit -m "feat: version KAPISCH managed profile state"
```

---

### Task 2: Separate Current Ownership, Drift, and Explicit Updates

**Files:**

- Modify: `plugins/kapisch/scripts/setup_profile.py:285-482`
- Modify: `plugins/kapisch/tests/kapisch_validation/test_setup_profile.py:671-918`

**Interfaces:**

- Consumes: `CURRENT_PROFILE_STATE_VERSION`, normalized `template_digest`, current `desired_digest`, and resolved routing fields from Task 1
- Produces: `_is_sha256(value: object) -> bool`
- Produces plan keys: `drift`, `template_drift`, `update_required`, `switch_required`, and `installed_profile_set`
- Preserves CLI authorization: only `--install --replace-managed` performs current replacement.

- [ ] **Step 1: Add failing same-set update and changed-routing update tests**

Add `ProfileSetTests.test_same_set_template_update_requires_explicit_replace`:

```python
    def test_same_set_template_update_requires_explicit_replace(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            revised_agents = project / "revised-agents"
            shutil.copytree(setup_profile.AGENT_DIR, revised_agents)
            reviewer = revised_agents / "kapisch-reviewer.toml"
            reviewer.write_bytes(
                reviewer.read_bytes().replace(b"\r\n", b"\n")
                + b"# current template revision\n"
            )

            inspect_output = io.StringIO()
            with (
                mock.patch.object(setup_profile, "AGENT_DIR", revised_agents),
                redirect_stdout(inspect_output),
            ):
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--role",
                            "reviewer",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "balanced",
                        ]
                    ),
                    0,
                )
            self.assertEqual(self._snapshot(project), before)
            self.assertIn("update_required=true", inspect_output.getvalue())
            self.assertIn(
                "rerun with --install --replace-managed",
                inspect_output.getvalue(),
            )

            with (
                mock.patch.object(setup_profile, "AGENT_DIR", revised_agents),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--role",
                            "reviewer",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "balanced",
                            "--install",
                            "--replace-managed",
                        ]
                    ),
                    0,
                )
            self.assertIn(
                b"# current template revision\n",
                (project / ".codex/agents/kapisch-reviewer.toml").read_bytes(),
            )
```

Add `ProfileSetTests.test_changed_current_routing_is_a_supported_update`:

```python
    def test_changed_current_routing_is_a_supported_update(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            routing = {
                name: dict(values)
                for name, values in setup_profile.PROFILE_SET_ROUTING.items()
            }
            routing["balanced"]["reviewer"] = ("gpt-5.6-terra", "low")
            before = self._snapshot(project)

            output = io.StringIO()
            with (
                mock.patch.object(setup_profile, "PROFILE_SET_ROUTING", routing),
                redirect_stdout(output),
            ):
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--role",
                            "reviewer",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "balanced",
                        ]
                    ),
                    0,
                )
            self.assertEqual(self._snapshot(project), before)
            self.assertIn("update_required=true", output.getvalue())

            with (
                mock.patch.object(setup_profile, "PROFILE_SET_ROUTING", routing),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--role",
                            "reviewer",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "balanced",
                            "--install",
                            "--replace-managed",
                        ]
                    ),
                    0,
                )
            profile = tomllib.loads(
                (project / ".codex/agents/kapisch-reviewer.toml").read_text(
                    encoding="utf-8"
                )
            )
            state = tomllib.loads(
                (project / ".kapisch/local-state/profiles/reviewer.toml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(profile["model_reasoning_effort"], "low")
            self.assertEqual(state["installed_model_reasoning_effort"], "low")
```

Rewrite `test_recorded_profile_set_must_match_installed_runtime_routing` as
`test_recorded_installed_routing_must_match_the_owned_profile`. Install
`balanced`, change only `installed_model_reasoning_effort="high"` to
`installed_model_reasoning_effort="low"` in the reviewer record, and assert
inspection and replacement both exit 2, preserve the snapshot, and print
`state record installed routing does not match the installed profile`.

Add `test_all_completes_wholly_absent_pairs_beside_current_desired_roles`:
install only `reviewer` with `balanced`, run `--all --profile-set balanced
--install`, assert exit 0, then assert exactly six profile files and six current
state records exist.

Add `test_all_rejects_missing_pairs_mixed_with_current_updates`: install only
`reviewer` with `balanced`, snapshot, run `--all --profile-set quality --install
--replace-managed`, and assert exit 2, exact snapshot equality, and
`cannot combine missing installs with managed replacements` in stdout.

- [ ] **Step 2: Run the five focused tests and verify failure**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_same_set_template_update_requires_explicit_replace \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_changed_current_routing_is_a_supported_update \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_recorded_installed_routing_must_match_the_owned_profile \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_all_completes_wholly_absent_pairs_beside_current_desired_roles \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_all_rejects_missing_pairs_mixed_with_current_updates \
  -v
```

Expected: FAIL because same-set/routing updates are not classified, current
records do not yet validate their stored installed routing, and the two partial
catalog outcomes are not yet proven.

- [ ] **Step 3: Add strict digest validation**

Add near `digest`:

```python
def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
```

Use `_is_sha256` for current record `template_sha256` and `installed_sha256`
instead of checking only `isinstance(..., str)`.

- [ ] **Step 4: Replace current routing inference with recorded installed routing**

After current-record identity/path/version validation in `_prepare_role`, read:

```python
        installed_model = saved.get("installed_model")
        installed_effort = saved.get("installed_model_reasoning_effort")
        if (
            not isinstance(installed_model, str)
            or not isinstance(installed_effort, str)
            or (
                installed_values.get("model"),
                installed_values.get("model_reasoning_effort"),
            )
            != (installed_model, installed_effort)
        ):
            plan.update(
                status="collision",
                error=(
                    "state record installed routing does not match "
                    "the installed profile"
                ),
            )
            return plan
```

Keep `profile_set` closed to `PROFILE_SET_CATALOG`, but do not require the
installed profile to equal today's routing for that set.

- [ ] **Step 5: Classify drift and desired updates independently**

Replace the old `installed_profile_set != profile_set`-only switch branch with:

```python
        plan.update(
            installed_profile_set=installed_profile_set,
            installed_bytes=installed_bytes,
            record_original_bytes=record_bytes,
        )
        plan["drift"] = (
            "none"
            if saved["installed_sha256"] == installed_digest
            else "user-modified"
        )
        plan["template_drift"] = (
            "none"
            if saved["template_sha256"] == template_digest
            else "updated"
        )
        update_required = (
            installed_profile_set != profile_set
            or saved["template_sha256"] != template_digest
            or installed_digest != desired_digest
        )
        plan["update_required"] = update_required
        plan["switch_required"] = update_required

        if install and replace_managed and plan["drift"] != "none":
            plan.update(
                status="collision",
                error=(
                    "managed replacement refused because "
                    "the installed profile drifted"
                ),
            )
            return plan
        if update_required and install and replace_managed:
            plan["record_bytes"] = _record_text(
                template=template,
                template_digest=template_digest,
                target=target,
                scope=scope,
                role=role,
                profile_set=profile_set,
                installed_digest=desired_digest,
            ).encode("utf-8")
            plan["status"] = "replace-pending"
            return plan
        plan["status"] = "installed"
        return plan
```

Retain the existing encoding exception handling around `_record_text`.

Update `_print_plan` to print:

```python
    if plan.get("update_required") is not None:
        print(
            "update_required="
            + ("true" if plan["update_required"] else "false")
        )
```

The action remains `rerun with --install --replace-managed after human review`
when `switch_required` is true.

- [ ] **Step 6: Run current-format focused and regression tests**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_same_set_template_update_requires_explicit_replace \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_changed_current_routing_is_a_supported_update \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_recorded_installed_routing_must_match_the_owned_profile \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_all_completes_wholly_absent_pairs_beside_current_desired_roles \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_all_rejects_missing_pairs_mixed_with_current_updates \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_managed_switch_requires_explicit_replace_and_updates_all_state \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_switch_refuses_a_user_modified_managed_profile \
  -v
```

Then run the full setup module:

```bash
python -m unittest tests.kapisch_validation.test_setup_profile -v
```

Expected: every focused test and the full setup module PASS. Inspection and
ordinary install are non-mutating; explicit undrifted replacement updates
profile and state; drift remains blocked. Do not commit Task 2 with a failing
setup test.

- [ ] **Step 7: Commit current update behavior**

```bash
git add \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py
git commit -m "feat: support explicit current profile updates"
```

---

### Task 3: Reject Legacy Profiles and Remove Profile Compatibility Assets

**Files:**

- Modify: `plugins/kapisch/scripts/setup_profile.py:5-12,129-192,217-246,285-482,1109-1203`
- Modify: `plugins/kapisch/tests/kapisch_validation/test_setup_profile.py:399-918,1730-1751`
- Verify absent: `plugins/kapisch/tests/fixtures/legacy-1.0.1/`

**Interfaces:**

- Produces: `_legacy_profile_binding_matches(saved: dict[str, Any], *, expected_identity: str, target: Path, scope: str) -> bool`
- Produces status: `unsupported-legacy`
- Produces output keys: `modified=false`, `legacy_profile`, `legacy_state_record`, and `guidance`
- Consumes: current state fields and ownership/update behavior from Tasks 1-2
- Removes: `_template_provenance_matches` and historical absolute-path imports.

- [ ] **Step 1: Add failing structural legacy-rejection tests**

Add a test helper to `ProfileSetTests`:

```python
    def _remove_profile_state_version(self, record: Path) -> None:
        lines = [
            line
            for line in record.read_text(encoding="utf-8").splitlines()
            if not line.startswith("profile_state_version=")
        ]
        record.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

Replace `test_verified_legacy_state_is_inspectable_as_quality_without_rewrite`
with:

```python
    def test_structural_legacy_state_is_rejected_without_mutation(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "quality"), 0)
            for record in (project / ".kapisch/local-state/profiles").glob("*.toml"):
                self._remove_profile_state_version(record)
            before = self._snapshot(project)
            output = io.StringIO()

            with redirect_stdout(output):
                self.assertEqual(
                    setup_profile.main(
                        ["--all", "--project-dir", str(project)]
                    ),
                    2,
                )

            self.assertEqual(self._snapshot(project), before)
            self.assertEqual(output.getvalue().count("status=unsupported-legacy"), 6)
            self.assertEqual(output.getvalue().count("modified=false"), 6)
            self.assertIn(
                f"legacy_profile={project / '.codex/agents/kapisch-reviewer.toml'}",
                output.getvalue(),
            )
            self.assertIn(
                "legacy_state_record="
                f"{project / '.kapisch/local-state/profiles/reviewer.toml'}",
                output.getvalue(),
            )
            self.assertIn(
                "docs/compatibility.md#legacy-profile-cleanup",
                output.getvalue().replace("\\", "/"),
            )
```

Add `test_legacy_binding_mismatch_is_an_ambiguous_collision` by installing
`quality`, removing the reviewer's state version, replacing its
`installed_profile` value with the architect target path, snapshotting, and
asserting exit 2, unchanged bytes, `status=collision`, and no
`status=unsupported-legacy`.

Add `test_older_profile_state_version_is_legacy` by installing one reviewer,
rewriting its integer `profile_state_version` from 1 to 0 without changing any
other field, snapshotting, and asserting the same non-mutating
`unsupported-legacy` result and exact paths.

Add `test_newer_profile_state_version_is_a_collision` by installing one
reviewer, rewriting its integer version from 1 to 2, snapshotting, and asserting
exit 2, exact snapshot equality, `status=collision`, and no
`status=unsupported-legacy`.

Add `test_mixed_current_and_legacy_catalog_rejects_atomically` by installing
`balanced`, removing only the reviewer record version, requesting a full-catalog
`quality --install --replace-managed`, and asserting exit 2 plus complete
snapshot equality.

Add `test_profile_and_record_only_states_are_inconsistent` with two subtests:
one deletes the reviewer state record and one deletes the reviewer profile.
Each inspection must exit 2, preserve the remaining snapshot, and report the
existing precise error (`installed profile has no verifiable state record` or
`state record exists without an installed profile`).

- [ ] **Step 2: Run the new legacy tests and verify failure**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_structural_legacy_state_is_rejected_without_mutation \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_binding_mismatch_is_an_ambiguous_collision \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_older_profile_state_version_is_legacy \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_newer_profile_state_version_is_a_collision \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_mixed_current_and_legacy_catalog_rejects_atomically \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_profile_and_record_only_states_are_inconsistent \
  -v
```

Expected: FAIL because unversioned records are still accepted through the old
quality compatibility branch and no generic legacy diagnostic exists.

- [ ] **Step 3: Add structural recognition that grants diagnostics only**

Add beside the record helpers:

```python
def _legacy_profile_binding_matches(
    saved: dict[str, Any],
    *,
    expected_identity: str,
    target: Path,
    scope: str,
) -> bool:
    return (
        saved.get("profile_identity") == expected_identity
        and saved.get("installed_profile") == str(target)
        and saved.get("scope") == scope
    )
```

After parsing both an existing target and its record, classify the version
before current ownership validation:

```python
        state_version = saved.get("profile_state_version")
        legacy_version = state_version is None or (
            type(state_version) is int
            and state_version < CURRENT_PROFILE_STATE_VERSION
        )
        if legacy_version:
            if _legacy_profile_binding_matches(
                saved,
                expected_identity=expected_identity,
                target=target,
                scope=scope,
            ):
                plan.update(
                    status="unsupported-legacy",
                    error="unsupported legacy KAPISCH profile state was detected",
                    legacy_profile=target,
                    legacy_state_record=record,
                )
            else:
                plan.update(
                    status="collision",
                    error="legacy-looking state bindings cannot be verified",
                )
            return plan
        if (
            type(state_version) is not int
            or state_version != CURRENT_PROFILE_STATE_VERSION
        ):
            plan.update(
                status="collision",
                error="state record has an unsupported profile state version",
            )
            return plan
```

This branch must not compare old template paths, profile sets, routing, or
hashes.

- [ ] **Step 4: Make current provenance exact and print actionable rejection output**

Delete `_template_provenance_matches`. Remove `PurePosixPath` and
`PureWindowsPath` from imports. In current record validation require every
binding independently, including:

```python
saved.get("profile_identity") == expected_identity
saved.get("installed_profile") == str(target)
saved.get("scope") == scope
saved.get("template") == template.name
```

Keep exact profile-set, installed-routing, and SHA-256 checks from Task 2. A
missing, wrongly typed, contradictory, or extra-version state value must never
establish ownership.

In `_print_plan`, add a leading legacy branch before other actions:

```python
    if plan["status"] == "unsupported-legacy":
        print("modified=false")
        print(f"legacy_profile={plan['legacy_profile']}")
        print(f"legacy_state_record={plan['legacy_state_record']}")
        print(
            "action=back up and manually remove the listed legacy files, "
            "then reinstall"
        )
        guidance = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "compatibility.md"
        )
        print(f"guidance={guidance}#legacy-profile-cleanup")
```

Ensure the remaining action chain uses `elif` so a legacy plan does not also
print a generic review action.

In `_run_setup`, collect both failure states:

```python
    failures = [
        plan
        for plan in plans
        if plan["status"] in {"collision", "unsupported-legacy"}
    ]
```

Keep exit code 2 whenever `failures` is non-empty.

- [ ] **Step 5: Remove old profile compatibility tests and rewrite relocation coverage**

Delete:

- the old `ProfileSetTests.test_verified_legacy_state_is_inspectable_as_quality_without_rewrite` method while replacing it in Step 1;
- every `legacy=True` case and version-field removal branch from
  `test_relocated_template_provenance_keeps_managed_sets_switchable`;
- `test_template_provenance_rejects_unrelated_versioned_paths`.

Rename the relocation test to
`test_current_filename_provenance_survives_plugin_cache_relocation`. Its cases
must cover project/user and single/catalog current records only. Install while
`AGENT_DIR` points to `temporary_root / "cache-a/agents"`, inspect and update
while it points to `temporary_root / "cache-b/agents"`, and assert every state
record contains:

```python
self.assertEqual(state["template"], f"kapisch-{role}.toml")
```

Add `test_current_template_provenance_requires_the_stable_filename`: install a
reviewer, replace `template="kapisch-reviewer.toml"` with an absolute Unix path,
and assert exit 2, unchanged snapshot, and
`state record identity or template provenance cannot be verified`.

- [ ] **Step 6: Run legacy, provenance, drift, and catalog tests**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_structural_legacy_state_is_rejected_without_mutation \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_binding_mismatch_is_an_ambiguous_collision \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_older_profile_state_version_is_legacy \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_newer_profile_state_version_is_a_collision \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_mixed_current_and_legacy_catalog_rejects_atomically \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_profile_and_record_only_states_are_inconsistent \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_current_filename_provenance_survives_plugin_cache_relocation \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_current_template_provenance_requires_the_stable_filename \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_switch_refuses_a_user_modified_managed_profile \
  -v
python -m unittest tests.kapisch_validation.test_setup_profile -v
```

Expected: every focused test and the full setup module PASS, with no filesystem
delta for every rejected case. Do not commit Task 3 with a failing setup test.

- [ ] **Step 7: Verify forbidden PR #35 profile assets are absent**

Run from the repository root:

```bash
test ! -e plugins/kapisch/tests/fixtures/legacy-1.0.1
if rg -n \
  "LEGACY_1_0_1_TEMPLATE_DIGESTS|verified legacy quality profile" \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py; then
  exit 1
fi
```

Expected: exit 0 and no matches.

- [ ] **Step 8: Commit legacy profile refusal and removal**

```bash
git add \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py
git commit -m "feat: reject legacy KAPISCH profile state"
```

---

### Task 4: Reset Transaction Compatibility to Current Journal Schema 3

**Files:**

- Modify: `plugins/kapisch/scripts/setup_profile.py:500-751,754-996,1100-1241`
- Modify: `plugins/kapisch/tests/kapisch_validation/test_setup_profile.py:466-542,890-1751`

**Interfaces:**

- Consumes: `CURRENT_SWITCH_JOURNAL_VERSION = 3`
- Produces: `_read_switch_state_version(path: Path) -> int` for the two existing journal/preparation paths only
- Preserves: `_switch_recovery_needed(root: Path) -> bool`
- Preserves: `_read_switch_journal(root: Path) -> tuple[str, list[dict[str, Any]]]`, restricted to schema 3
- Preserves: `_recover_interrupted_switch(root: Path) -> tuple[bool, str | None]`, restricted to schema 3 journals
- Removes: schema-1/schema-2 recovery and deterministic `.recover.tmp` fallback.
- Explicitly does not add global orphan discovery, artifact globbing, or new lock architecture.

- [ ] **Step 1: Convert current recovery helpers and assertions to schema 3**

In `_interrupt_prepared_switch`, retain the existing current transaction setup
and add:

```python
        self.assertEqual(tomllib.loads(journal.read_text())["version"], 3)
```

Change every existing assertion that treats a newly generated journal as version
2 to expect version 3. Do not change tests for synthetic legacy rejection added
below.

- [ ] **Step 2: Add failing fixed-path version-boundary tests**

Keep fixtures inline. Do not add historical profile bytes, digest allowlists, or
artifact scanners.

Add `test_legacy_switch_journal_versions_are_not_recovered`:

```python
    def test_legacy_switch_journal_versions_are_not_recovered(self) -> None:
        for version in (1, 2):
            with self.subTest(version=version), TemporaryDirectory() as temporary:
                project = Path(temporary).resolve()
                self.assertEqual(self._install(project, "balanced"), 0)
                self._interrupt_prepared_switch(project)
                journal = project / ".kapisch/local-state/profile-switch.toml"
                legacy_bytes = journal.read_bytes()
                if version == 1:
                    legacy_bytes = b"".join(
                        line
                        for line in legacy_bytes.splitlines(keepends=True)
                        if not line.startswith(b"recovery=")
                    )
                journal.write_bytes(
                    legacy_bytes.replace(
                        b"version=3\n",
                        f"version={version}\n".encode("ascii"),
                        1,
                    )
                )
                before = self._snapshot(project)
                output = io.StringIO()

                with redirect_stdout(output):
                    self.assertEqual(
                        setup_profile.main(
                            ["--all", "--project-dir", str(project)]
                        ),
                        2,
                    )

                self.assertEqual(self._snapshot(project), before)
                self.assertIn("status=unsupported-legacy", output.getvalue())
                self.assertIn("modified=false", output.getvalue())
                self.assertIn(f"legacy_journal={journal}", output.getvalue())
```

Add `test_legacy_switch_preparation_versions_are_not_removed` with the same
`for version in (1, 2)` fixture conversion, but rename the journal to the
existing `.profile-switch.prepare.tmp` path before snapshotting. Each subtest
must exit 2, preserve the complete snapshot byte-for-byte, print
`status=unsupported-legacy`, `modified=false`, and the exact
`legacy_prepare=<path>`.

Add `test_malformed_and_newer_switch_journals_are_preserved` with two subtests.
After a balanced install, write either syntactically invalid TOML or a copy of a
current journal with integer `version=4` to `profile-switch.toml`. Inspection
must exit 2 with `status=collision`, preserve the exact snapshot, and never print
`status=unsupported-legacy`.

- [ ] **Step 3: Run the new boundary tests and verify intended failures**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_switch_journal_versions_are_not_recovered \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_switch_preparation_versions_are_not_removed \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_malformed_and_newer_switch_journals_are_preserved \
  -v
```

Expected: FAIL because schemas 1-2 still enter recovery, the current writer does
not yet emit schema 3, and legacy preparation files are still removed.

- [ ] **Step 4: Make `_switch_journal_text` emit schema 3 only**

Replace version inference with the current constant and require every entry to
carry a recovery path:

```python
def _switch_journal_text(status: str, entries: list[dict[str, Any]]) -> bytes:
    if not entries or any("recovery" not in entry for entry in entries):
        raise ValueError("current profile-switch entries require recovery paths")
    lines = [
        f"version={CURRENT_SWITCH_JOURNAL_VERSION}\n",
        f"status={toml_basic_string(status)}\n",
    ]
```

Keep the existing eight entry fields and TOML rendering loop.

- [ ] **Step 5: Restrict `_read_switch_journal` to schema 3**

Keep `_read_switch_journal(root)` and its fixed journal path. Replace the
schema-1/schema-2 version branches with one exact current check:

```python
    version = values.get("version")
    status = values.get("status")
    if (
        type(version) is not int
        or version != CURRENT_SWITCH_JOURNAL_VERSION
        or type(status) is not str
        or status not in {"prepared", "committed"}
    ):
        raise OSError("profile-switch journal has an unsupported version or status")
```

Use the current eight-field entry shape unconditionally:

```python
    expected_fields = {
        "role",
        "kind",
        "destination",
        "backup",
        "staged",
        "recovery",
        "original_sha256",
        "desired_sha256",
    }
```

Retain the existing non-empty entry, unique role/kind, derived
profile/state/backup/staged path, random-token recovery path, and digest checks.
Delete only version-specific schema-1/schema-2 branches; do not redesign current
schema-3 validation or recovery.

- [ ] **Step 6: Gate only the existing journal and preparation paths by version**

Add one small parser for the two paths already checked by
`_switch_recovery_needed`:

```python
def _read_switch_state_version(path: Path) -> int:
    if path.is_symlink():
        raise OSError("profile-switch state is a symbolic link")
    values = _parse_profile_bytes(path.read_bytes())
    version = values.get("version")
    if type(version) is not int:
        raise OSError("profile-switch state has an invalid version")
    return version
```

In `_run_setup`, after its existing `recovery_needed`/`allow_recovery` guard and
before `_recover_interrupted_switch`, inspect only `_switch_journal_path(root)`
and `_switch_prepare_path(root)` when they exist. Keep `main`,
`_switch_recovery_needed`, and `_switch_lock` unchanged.

For either fixed path:

- version 1 or 2: print `status=unsupported-legacy`, `modified=false`, the exact
  `legacy_journal=<path>` or `legacy_prepare=<path>`, manual backup/removal
  guidance, and return 2 before recovery;
- version 3: continue through existing recovery behavior;
- malformed TOML, a missing/non-integer version, symlink, or any version other
  than 1-3: print `status=collision`, `modified=false`, and return 2 without
  recovery.

If both fixed paths exist, inspect both before allowing recovery so a legacy or
collision preparation file cannot be removed as cleanup for a current journal.
Do not parse legacy entries, derive their referenced paths, scan sibling
directories, enumerate backup/staged/recovery artifacts, or introduce a new
transaction classifier. Current schema-3 journal validation remains in
`_read_switch_journal`; current schema-3 preparation cleanup retains the
existing under-lock behavior.

- [ ] **Step 7: Remove deterministic schema-1 recovery fallback**

In `_recovery_staging_path` and `_recover_interrupted_switch`, delete branches
and comments for entries without `recovery`, including deterministic
`.kapisch-switch.recover.tmp` handling. Every recovered entry now gets its
random-token path from the validated schema-3 journal.

Keep `_is_owned_recovery_staging` for partial writes to that journal-bound random
path. It is current transaction safety, not legacy compatibility.

Delete from tests:

- `_legacy_prepared_switch`;
- `test_legacy_partial_recovery_staging_recovers_automatically`;
- `test_legacy_unverified_recovery_staging_fails_closed`.

The new schema-1/schema-2 refusal tests replace those compatibility tests.

- [ ] **Step 8: Run focused and full transaction recovery tests**

Run from `plugins/kapisch`:

```bash
python -m unittest \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_switch_journal_versions_are_not_recovered \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_legacy_switch_preparation_versions_are_not_removed \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_malformed_and_newer_switch_journals_are_preserved \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_transaction_owned_partial_recovery_staging_recovers_automatically \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_unverified_recovery_staging_fails_closed \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_interrupted_switch_recovers_at_every_profile_and_state_publish \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_interrupted_switch_preserves_a_later_user_edit \
  tests.kapisch_validation.test_setup_profile.ProfileSetTests.test_interrupted_journal_publish_recovers_and_commit_publish_finishes \
  -v
python -m unittest tests.kapisch_validation.test_setup_profile -v
```

Expected: all focused and full setup tests PASS. Schema-1/schema-2 journal and
preparation files remain byte-for-byte unchanged; malformed/newer journals fail
closed; existing schema-3 interruption, external-edit, cleanup, and concurrency
semantics remain green.

- [ ] **Step 9: Commit the transaction boundary reset**

```bash
git add \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py
git commit -m "feat: reset KAPISCH profile transaction compatibility"
```

---

### Task 5: Publish the 2.0.0 Documentation and Release Contract

**Files:**

- Modify: `tests/test_marketplace.py:19-130`
- Modify: `README.md`
- Modify: `plugins/kapisch/README.md`
- Modify: `plugins/kapisch/docs/compatibility.md`
- Modify: `plugins/kapisch/docs/profile-sets.md`
- Modify: `plugins/kapisch/docs/acceptance.md`
- Modify: `plugins/kapisch/CONTRIBUTING.md`
- Modify: `plugins/kapisch/CHANGELOG.md`
- Modify: `plugins/kapisch/.codex-plugin/plugin.json`
- Modify: `plugins/kapisch/pyproject.toml`
- Create: `plugins/kapisch/docs/acceptance-windows-v2.0.0.md`

**Interfaces:**

- Consumes: completed runtime commits from Tasks 1-4 and their actual validation evidence
- Produces: synchronized release `2.0.0`
- Produces: stable documentation anchor `#legacy-profile-cleanup`
- Produces: version-generic release provenance checks
- Preserves: canonical marketplace source and immutable release-ref policy.

- [ ] **Step 1: Capture actual runtime evidence from Tasks 1-4**

Before changing tests, documentation, or release metadata, run from the
repository root:

```bash
git status --short
RUNTIME_SHA="$(git rev-parse HEAD)"
printf 'Tested runtime SHA: %s\n' "$RUNTIME_SHA"
python -m unittest discover -s tests
(
  cd plugins/kapisch
  python -m unittest discover -s tests/kapisch_validation
  python scripts/test_portable_package.py
  python scripts/validate_kapisch.py --help
)
```

Expected: working tree clean; `RUNTIME_SHA` is a 40-character commit from Task
4; every command exits 0. Record the exact observed total pass and
platform-capability-skip counts for the acceptance document. Do not invent CI
success or a final release SHA.

- [ ] **Step 2: Generalize release provenance checks before changing versions**

Delete `MarketplaceTests.TESTED_RUNTIME_SHA`. Replace
`assert_release_provenance` with:

```python
    def assert_release_provenance(self, matrix: str, acceptance: str) -> None:
        match = re.search(
            r"^- Tested runtime SHA: `([0-9a-f]{40})`\.$",
            acceptance,
            re.MULTILINE,
        )
        self.assertIsNotNone(match)
        tested_runtime_sha = match.group(1)
        self.assertIn(
            f"tested runtime tree `{tested_runtime_sha}`",
            matrix,
        )
        self.assertIn("final release SHA pending", matrix)
        self.assertNotIn("current uncommitted candidate worktree", matrix)
        self.assertIn(
            "automated evidence is bound to this exact runtime tree",
            acceptance,
        )
        self.assertRegex(
            acceptance,
            r"[0-9]+ passed,\s+[0-9]+ platform-capability skips",
        )
        self.assertIn(
            "- Final release SHA: pending review, merge, and authorized release preparation.",
            acceptance,
        )
        self.assertNotIn("current uncommitted candidate worktree", acceptance)
```

Run from the repository root:

```bash
python -m unittest tests.test_marketplace.MarketplaceTests.test_release_metadata_is_consistent -v
```

Expected: PASS against the existing 1.2.1 documentation, proving the check is
version-generic before the release bump.

- [ ] **Step 3: Add a failing current-documentation contract test**

Add `MarketplaceTests.test_current_profile_docs_describe_the_legacy_boundary`:

```python
    def test_current_profile_docs_describe_the_legacy_boundary(self) -> None:
        expectations = {
            ROOT / "README.md": ("v2.0.0", "legacy profile"),
            PLUGIN / "README.md": ("profile_state_version", "manual cleanup"),
            PLUGIN / "docs/compatibility.md": (
                "profile_state_version = 1",
                "## Legacy profile cleanup",
            ),
            PLUGIN / "docs/profile-sets.md": (
                "--install --replace-managed",
                "unsupported legacy",
            ),
            PLUGIN / "docs/acceptance.md": (
                "2.0.0",
                "historical",
            ),
            PLUGIN / "CONTRIBUTING.md": (
                "historical profile bytes",
                "automatic migration",
            ),
        }
        for path, required in expectations.items():
            with self.subTest(path=path):
                contents = path.read_text(encoding="utf-8")
                for phrase in required:
                    self.assertIn(phrase, contents)

        current_compatibility = (
            PLUGIN / "docs/compatibility.md"
        ).read_text(encoding="utf-8")
        for obsolete in (
            "inspection reports it as legacy",
            "legacy `quality`",
            "unverifiable legacy digest",
        ):
            self.assertNotIn(obsolete, current_compatibility)
```

Keep this negative check scoped to the current compatibility page; historical
changelog and acceptance records must retain their old evidence.

Run:

```bash
python -m unittest \
  tests.test_marketplace.MarketplaceTests.test_current_profile_docs_describe_the_legacy_boundary \
  -v
```

Expected: FAIL because current docs still describe 1.x compatibility and the
root install command still points to 1.2.1.

- [ ] **Step 4: Bump both version surfaces to 2.0.0**

Set:

```json
"version": "2.0.0"
```

in `plugins/kapisch/.codex-plugin/plugin.json`, and:

```toml
version = "2.0.0"
```

in `plugins/kapisch/pyproject.toml`.

Do not add a version to `.agents/plugins/marketplace.json`.

- [ ] **Step 5: Add the exact 2.0.0 changelog entry**

Prepend a `## 2.0.0 - 2026-09-06 (release candidate)` section to
`plugins/kapisch/CHANGELOG.md` that states:

- this is an intentional breaking change for locally managed profile/setup
  state only;
- profile-state schema 1 and switch-journal schema 3 are current and independent
  of plugin semver;
- legacy profiles and journal schemas 1-2 are detected and rejected without
  mutation;
- automatic legacy migration/recovery and old compatibility tests were removed;
- generated profiles normalize newlines and current undrifted profiles support
  explicit same-set/routing updates;
- six roles, identities, durable-run compatibility, validator behavior, and
  workflow authority are unchanged;
- release, review, final readiness, and tag creation remain pending.

Retain every historical changelog section unchanged below the new entry.

- [ ] **Step 6: Update both README installation and upgrade stories**

In `README.md` and `plugins/kapisch/README.md`, make the immutable command exactly:

```text
codex plugin marketplace add twKrash/kapisch --ref v2.0.0
```

Remove other immutable release-ref values from current instructions. Keep
mutable `main` labeled development-only.

In the plugin README's optional-profile section, document:

- fresh inspection and explicit install;
- `profile_state_version = 1` as current state, not plugin version;
- explicit same-set/profile-set updates through `--install --replace-managed`;
- drift and collision refusal;
- unsupported legacy state with no automatic migration;
- the manual cleanup link;
- plugin removal and optional profile removal as separate operations.

At the root README level, include a concise “legacy profile” warning and link to
the plugin compatibility cleanup section.

- [ ] **Step 7: Rewrite normative compatibility and profile-set documentation**

In `plugins/kapisch/docs/compatibility.md`:

- replace the current profile compatibility text that accepts verified 1.0.x
  records;
- define current profile-state schema 1 and switch-journal schema 3;
- state that release 2.0.0 established the boundary while runtime code remains
  semver-independent;
- distinguish structural legacy diagnosis from ownership;
- retain unrelated durable-run compatibility and migration sections unchanged;
- add the exact heading:

```markdown
## Legacy profile cleanup
```

Under that heading, provide POSIX and PowerShell procedures that prompt for one
installer-listed exact path at a time, so the examples contain no guessed path:

```bash
mkdir -p "$HOME/kapisch-profile-backup"
printf 'Paste one exact path printed by setup: '
IFS= read -r LEGACY_PATH
cp -- "$LEGACY_PATH" "$HOME/kapisch-profile-backup/"
printf 'Inspect the backup, then press Enter to remove the original.'
IFS= read -r _confirmation
rm -- "$LEGACY_PATH"
```

```powershell
New-Item -ItemType Directory -Force "$HOME\kapisch-profile-backup"
$LegacyPath = Read-Host "Paste one exact path printed by setup"
Copy-Item -LiteralPath $LegacyPath -Destination "$HOME\kapisch-profile-backup"
Read-Host "Inspect the backup, then press Enter to remove the original"
Remove-Item -LiteralPath $LegacyPath
```

Tell the user to repeat the sequence for each printed path, review every backup
before removal, and never delete `.kapisch` wholesale. Then show the existing
project/user inspection and install commands for reinstall.

In `plugins/kapisch/docs/profile-sets.md`, document:

- current inspection;
- same-set and profile-set update detection;
- explicit replacement;
- drift refusal;
- missing-plus-replacement catalog refusal;
- generic `unsupported legacy` outcome and cleanup link;
- current schema-3 recovery versus old-journal refusal.

- [ ] **Step 8: Update acceptance and contributor policy**

In `plugins/kapisch/docs/acceptance.md`:

- add a 2.0.0 candidate row using the Task 5 Step 1 runtime SHA;
- include the phrase `tested runtime tree` with that exact SHA;
- include `final release SHA pending`;
- label pre-2.0 Windows/release rows historical;
- replace “verified legacy quality records” as a current test claim with legacy
  refusal/no-mutation coverage;
- retain unrelated durable migration and platform history.

In `plugins/kapisch/CONTRIBUTING.md`, add a profile compatibility policy that
states:

- current profile-state formats are independent of plugin semver;
- unsupported legacy state is diagnostic-only;
- historical profile bytes, digest allowlists, and migration fixtures must not
  be introduced without a separately approved compatibility design;
- any future incompatible state-format change requires an intentional semver
  decision and updated Linux/native-Windows tests.

- [ ] **Step 9: Create the pending native-Windows acceptance record**

Create `plugins/kapisch/docs/acceptance-windows-v2.0.0.md` with this exact
release header and provenance fields:

```markdown
# Windows acceptance record — 2.0.0

**Status: PENDING.** This is the release-candidate acceptance record. Native
Windows automated CI is required; a separate native-PowerShell live acceptance
run is optional.

- Release: `2.0.0`; intended immutable tag: `v2.0.0`.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during candidate preparation.
```

Generate the tested-runtime line from the clean Task 4 commit and insert the
command's output immediately after the release line:

```bash
printf -- '- Tested runtime SHA: `%s`.\n' "$(git rev-parse HEAD)"
```

The printed value must be exactly 40 lowercase hexadecimal characters.

Include these sections:

- `## Compatibility boundary under test`
- `## Required automated evidence`
- `## Current candidate evidence — 2026-09-06`
- `## Native Windows CI expectation`
- `## Optional live acceptance`
- `## Release boundary`

The candidate-evidence section must sum the integer test totals reported by the
successful Step 1 commands, count the reported platform-capability skips, and
record those concrete integers in the phrase required by
`assert_release_provenance`. Include the sentence `automated evidence is bound
to this exact runtime tree`. Do not claim native Windows success before the
GitHub Actions job passes. Record the required Windows commands:

```text
python -m unittest discover -s tests/kapisch_validation -p test_setup_profile.py
python scripts/test_portable_package.py
```

- [ ] **Step 10: Run release and documentation tests**

Run from the repository root:

```bash
python -m unittest \
  tests.test_marketplace.MarketplaceTests.test_release_metadata_is_consistent \
  tests.test_marketplace.MarketplaceTests.test_current_profile_docs_describe_the_legacy_boundary \
  -v
python -m unittest tests.test_plugin_version_policy -v
python scripts/check_plugin_version.py --base origin/main
python -m unittest discover -s tests
(
  cd plugins/kapisch
  python -m unittest discover -s tests/kapisch_validation
  python scripts/test_portable_package.py
  python scripts/validate_kapisch.py --help
)
```

Expected: every selected test, complete root/plugin suite, package check, and
validator help command PASS. The version checker prints a pass from 1.2.1 to
2.0.0 with `material=True`. Do not commit Task 5 with a failing gate.

- [ ] **Step 11: Commit documentation and release metadata**

```bash
git add \
  README.md \
  plugins/kapisch/README.md \
  plugins/kapisch/docs/compatibility.md \
  plugins/kapisch/docs/profile-sets.md \
  plugins/kapisch/docs/acceptance.md \
  plugins/kapisch/docs/acceptance-windows-v2.0.0.md \
  plugins/kapisch/CONTRIBUTING.md \
  plugins/kapisch/CHANGELOG.md \
  plugins/kapisch/.codex-plugin/plugin.json \
  plugins/kapisch/pyproject.toml \
  tests/test_marketplace.py
git commit -m "docs: prepare KAPISCH 2.0.0 compatibility reset"
```

---

## Final Removal Audit

- [ ] Verify PR #35-only assets remain absent:

```bash
test ! -e plugins/kapisch/tests/fixtures/legacy-1.0.1
test ! -e plugins/kapisch/docs/acceptance-windows-v1.2.2.md
if rg -n \
  "plugins/kapisch/tests/fixtures/legacy-1.0.1" \
  .gitattributes; then
  exit 1
fi
```

Expected: exit 0 and no output. These are the assets associated with abandoned
PR #35 commits `af044921d91a1cb7a986acf1ae90516c915722a4` and
`eb50246ef0cb7891df034afb80475fbba31d8680`; do not cherry-pick either commit.

- [ ] Verify obsolete current-facing profile compatibility claims are gone while
  historical records remain untouched:

```bash
if rg -n \
  'inspection reports it as legacy|legacy `quality`|unverifiable legacy digest' \
  plugins/kapisch/README.md \
  plugins/kapisch/docs/compatibility.md \
  plugins/kapisch/docs/profile-sets.md; then
  exit 1
fi
```

Expected: exit 0 and no output. Do not run this negative search over changelog
or historical acceptance files.

- [ ] Verify old profile compatibility source and tests are gone:

```bash
if rg -n \
  "LEGACY_1_0_1_TEMPLATE_DIGESTS|_legacy_prepared_switch|test_verified_legacy_state_is_inspectable_as_quality_without_rewrite|test_legacy_partial_recovery_staging_recovers_automatically|test_legacy_unverified_recovery_staging_fails_closed|verified legacy quality profile" \
  plugins/kapisch/scripts/setup_profile.py \
  plugins/kapisch/tests/kapisch_validation/test_setup_profile.py; then
  exit 1
fi
```

Expected: exit 0 and no output.

- [ ] Verify runtime source is not coupled to plugin release 2.0:

```bash
if rg -n "2\\.0|pre-2\\.0|2\\.x" plugins/kapisch/scripts/setup_profile.py; then
  exit 1
fi
rg -n \
  "CURRENT_PROFILE_STATE_VERSION = 1|CURRENT_SWITCH_JOURNAL_VERSION = 3" \
  plugins/kapisch/scripts/setup_profile.py
```

Expected: first search has no matches; second search prints both named constants.

- [ ] Verify only intended files changed:

```bash
git diff --name-only origin/main...HEAD
```

Expected: only the runtime/test/documentation/metadata files listed in this plan,
plus the already-approved spec and this implementation plan. The intended
`tests/test_marketplace.py` provenance assertions may change, but there must be
no agent-template, CI, marketplace-manifest architecture, `.gitattributes`,
validator, durable migration, fixture, or release-tag changes.

## Final Verification Gate

Run every command from a clean working tree after all five task commits.

- [ ] Run proactive Python diagnostics if the execution harness provides an LSP,
  then run the complete Linux/root gates:

```bash
python -m unittest discover -s tests
(
  cd plugins/kapisch
  python -m unittest discover -s tests/kapisch_validation
  python scripts/test_portable_package.py
  python scripts/validate_kapisch.py --help
)
```

Expected: every command exits 0. Inspect the reported test counts and update the
pending acceptance record only if its recorded local evidence differs; if that
requires a documentation correction, commit it with:

```bash
git add \
  plugins/kapisch/docs/acceptance.md \
  plugins/kapisch/docs/acceptance-windows-v2.0.0.md
git commit -m "docs: reconcile KAPISCH 2.0.0 acceptance evidence"
```

- [ ] Run the version-policy and whitespace gates:

```bash
python scripts/check_plugin_version.py --base origin/main
git diff --check origin/main...HEAD
git status --short
```

Expected: version policy passes from 1.2.1 to 2.0.0; diff check emits no output;
working tree is clean.

- [ ] Confirm native Windows CI expectations without claiming unobserved success:

Required GitHub Actions job: `windows-profile-setup` on `windows-latest`, Python
3.11.

Required commands from `plugins/kapisch`:

```text
python -m unittest discover -s tests/kapisch_validation -p test_setup_profile.py
python scripts/test_portable_package.py
```

Expected before merge/release: both commands pass in the job. If the job has not
run, report it as pending. Do not weaken, skip, or mark the job optional; only the
separate manual native-PowerShell live flow is optional.

- [ ] Inspect the final diff directly:

```bash
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD
git log --oneline origin/main..HEAD
```

Expected logical commit sequence:

1. `feat: version KAPISCH managed profile state`
2. `feat: support explicit current profile updates`
3. `feat: reject legacy KAPISCH profile state`
4. `feat: reset KAPISCH profile transaction compatibility`
5. `docs: prepare KAPISCH 2.0.0 compatibility reset`
6. optional evidence-reconciliation documentation commit only when final local
   results changed the recorded evidence.

Do not push, open a PR, tag, publish, or release without separate authorization.

## Spec-to-Task Coverage Map

| Spec requirement | Implementation task or gate |
| --- | --- |
| Release-independent current profile-state schema | Task 1 |
| Version 2.0.0 semantic release decision | Task 5 |
| LF/CRLF deterministic generated output | Task 1 and Final Verification |
| Current ownership bindings and resolved routing | Tasks 1-2 |
| Same-set and changed-routing explicit updates | Task 2 |
| User drift preservation | Task 2 regression tests |
| Structural legacy recognition without historical bytes | Task 3 |
| No mutation on legacy rejection | Task 3 snapshot tests |
| Ambiguous and partial profile-state refusal | Task 3 |
| Removal of unversioned-quality compatibility and old provenance | Task 3 and Final Removal Audit |
| Journal schemas 1-2 rejected, not recovered | Task 4 |
| Current journal schema 3 recovery retained | Task 4 |
| Fixed-path schema-1/schema-2 refusal and malformed/newer journal collision | Task 4 |
| Removal of deterministic legacy recovery behavior/tests | Task 4 and Final Removal Audit |
| PR #35 fixtures, hashes, and `.gitattributes` rule remain absent | Tasks 3-4 and Final Removal Audit |
| Complete current-facing documentation | Task 5 documentation steps and test |
| Manual POSIX/PowerShell backup/remove/reinstall guidance | Task 5 |
| Historical records retained but labeled historical | Task 5 |
| Version metadata and release provenance synchronization | Task 5 and Final Verification |
| Native Windows CI remains required; manual PowerShell live flow optional | Task 5 and Final Verification |
| No durable-run, role, CI, dependency, or marketplace redesign | Global Constraints and Final Removal Audit |
| No automatic cleanup/migration command | Tasks 3-5 review and Final Removal Audit |
