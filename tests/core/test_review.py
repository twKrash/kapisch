import unittest

from kapisch_core.review import (
    EvidenceLocator,
    HostProvenanceAttestation,
    ImmutableArtifactLocator,
    ReviewerReturn,
    ReviewInvocation,
    ReviewResult,
)


class ReviewFormatTests(unittest.TestCase):
    def _locator(self, path="artifact.json"):
        return ImmutableArtifactLocator(path, "a" * 64)

    def _records(self):
        locator = self._locator
        invocation = ReviewInvocation(
            locator("bundle"), locator("request"),
            {"run_id": "run", "stage_id": "stage"},
            {"run_id": "run", "operation_id": "operation"},
            locator("scope"), "base", "head", "final", ["src/a"],
            locator("fingerprint"),
        )
        reviewer_return = ReviewerReturn(
            locator("invocation"), {"run_id": "run", "operation_id": "operation"},
            locator("request"), {
                "run_id": "run", "stage_id": "stage", "operation_id": "operation",
                "base": "base", "head": "head",
            }, locator("fingerprint"), locator("report"), "a" * 64, "clear",
        )
        attestation = HostProvenanceAttestation(
            locator("reviewer-return"), "a" * 64, {"host": "one"},
            ["context"], {"dispatch": True},
        )
        result = ReviewResult(
            locator("invocation"), locator("request"), {
                "run_id": "run", "stage_id": "stage", "operation_id": "operation",
                "base": "base", "head": "head",
            }, locator("scope"), locator("fingerprint"), locator("reviewer-return"),
            locator("post-result"), locator("provenance"),
        )
        return invocation, reviewer_return, attestation, result

    def test_composite_records_round_trip_and_project_nested_locators(self):
        for record in self._records():
            projected = record.to_dict()
            self.assertIsInstance(projected[next(iter(projected))], dict)
            restored = type(record).from_dict(projected)
            self.assertEqual(restored.canonical_bytes(), record.canonical_bytes())
            reordered = dict(reversed(list(projected.items())))
            self.assertEqual(type(record).from_dict(reordered).canonical_bytes(), record.canonical_bytes())

    def test_records_are_canonical_and_immutable(self):
        locator = ImmutableArtifactLocator("bundle.json", "a" * 64)
        self.assertEqual(locator.to_dict(), {"path": "bundle.json", "sha256": "a" * 64})
        with self.assertRaises(AttributeError):
            locator.path = "other"
        self.assertEqual(locator.canonical_bytes(), b'{"path":"bundle.json","sha256":"' + b"a" * 64 + b'"}\n')

    def test_closed_records_reject_unknown_fields(self):
        with self.assertRaises(ValueError):
            ImmutableArtifactLocator.from_dict({"path": "x", "sha256": "a" * 64, "extra": 1})
        with self.assertRaises(ValueError):
            ReviewInvocation.from_dict({})

    def test_nested_records_are_copied(self):
        value = {"path": "x", "sha256": "a" * 64}
        locator = EvidenceLocator.from_dict(value)
        value["path"] = "changed"
        self.assertEqual(locator.path, "x")

    def test_decision_and_purpose_are_closed_literals(self):
        invocation, reviewer_return, _, _ = self._records()
        with self.assertRaises(ValueError):
            ReviewerReturn(
                reviewer_return.invocation, reviewer_return.operation,
                reviewer_return.request, reviewer_return.target,
                reviewer_return.fingerprint, reviewer_return.report,
                reviewer_return.report_digest, [],
            )
        with self.assertRaises(ValueError):
            ReviewInvocation(
                invocation.retained_bundle, invocation.request,
                invocation.attempt, invocation.operation, invocation.scope,
                invocation.base, invocation.head, [], invocation.included_untracked,
                invocation.pre_dispatch_fingerprint,
            )

    def test_scalar_subclasses_and_unhashable_literals_are_rejected(self):
        class EvilString(str):
            def __hash__(self):
                return hash("clear")

        locator = self._locator()
        with self.assertRaises(ValueError):
            ImmutableArtifactLocator(EvilString("x"), "a" * 64)
        with self.assertRaises(ValueError):
            ImmutableArtifactLocator.from_dict({"path": EvilString("x"), "sha256": "a" * 64})
        with self.assertRaises(ValueError):
            ReviewerReturn(
                locator, {"run_id": "r", "operation_id": "o"}, locator,
                {"run_id": "r", "stage_id": "s", "operation_id": "o",
                 "base": "b", "head": "h"}, locator, locator, "a" * 64,
                EvilString("clear"),
            )
        with self.assertRaises(ValueError):
            ReviewerReturn(
                locator, {"run_id": "r", "operation_id": "o"}, locator,
                {"run_id": "r", "stage_id": "s", "operation_id": "o",
                 "base": "b", "head": "h"}, locator, locator, "a" * 64,
                [],
            )

    def test_canonical_freezing_rejects_surrogates_cycles_and_unsupported_values(self):
        locator = self._locator()
        bad_values = [chr(0xD800), {chr(0xD800): "value"}, float("nan"), object()]
        for bad in bad_values:
            with self.assertRaises(ValueError):
                HostProvenanceAttestation(locator, "a" * 64, bad, {}, {})
            raw = HostProvenanceAttestation(locator, "a" * 64, {}, {}, {}).to_dict()
            raw["execution_identity"] = bad
            with self.assertRaises(ValueError):
                HostProvenanceAttestation.from_dict(raw)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            HostProvenanceAttestation(locator, "a" * 64, cycle, {}, {})

    def test_review_result_requires_matching_fingerprint_and_post_result_digest(self):
        _, _, _, result = self._records()
        mismatched = ImmutableArtifactLocator("post-result", "b" * 64)
        with self.assertRaises(ValueError):
            ReviewResult(
                result.invocation, result.request, result.target, result.scope,
                result.fingerprint, result.reviewer_return, mismatched,
                result.provenance,
            )
        raw = result.to_dict()
        raw["post_result"]["sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            ReviewResult.from_dict(raw)

    def test_loader_outer_keys_require_exact_utf8_strings(self):
        class StringAlias(str):
            pass

        class MappingAlias:
            def __hash__(self):
                return hash("path")

            def __eq__(self, other):
                return other == "path"

        valid = {"path": "x", "sha256": "a" * 64}
        for key in (StringAlias("path"), MappingAlias()):
            value = dict(valid)
            value.pop("path")
            value[key] = "x"
            with self.assertRaises(ValueError):
                ImmutableArtifactLocator.from_dict(value)
        invocation, _, _, _ = self._records()
        value = invocation.to_dict()
        value[StringAlias("base")] = value.pop("base")
        with self.assertRaises(ValueError):
            ReviewInvocation.from_dict(value)

    def test_mapping_guards_reject_alias_keys_in_constructors_and_loaders(self):
        class StringAlias(str):
            pass

        class MappingAlias:
            def __hash__(self):
                return hash("run_id")

            def __eq__(self, other):
                return other == "run_id"

        invocation, reviewer_return, _, result = self._records()
        cases = (
            (invocation, "attempt"),
            (invocation, "operation"),
            (reviewer_return, "operation"),
            (reviewer_return, "target"),
            (result, "target"),
        )
        for record, field in cases:
            for alias in (StringAlias("run_id"), MappingAlias()):
                value = dict(getattr(record, field))
                value[alias] = value.pop("run_id")
                arguments = {
                    name: getattr(record, name)
                    for name in record.__dataclass_fields__
                }
                arguments[field] = value
                with self.assertRaises(ValueError):
                    type(record)(**arguments)
                raw = record.to_dict()
                raw[field] = value
                with self.assertRaises(ValueError):
                    type(record).from_dict(raw)

    def test_nested_host_facts_reject_alias_keys_in_constructors_and_loaders(self):
        class StringAlias(str):
            pass

        class MappingAlias:
            def __hash__(self):
                return hash("fact")

            def __eq__(self, other):
                return other == "fact"

        locator = self._locator()
        valid = HostProvenanceAttestation(locator, "a" * 64, {}, {}, {})
        for alias in (StringAlias("fact"), MappingAlias()):
            for field in ("execution_identity", "execution_context", "dispatch_facts"):
                value = {"nested": {alias: True}}
                arguments = {
                    name: getattr(valid, name)
                    for name in valid.__dataclass_fields__
                }
                arguments[field] = value
                with self.assertRaises(ValueError):
                    HostProvenanceAttestation(**arguments)
                raw = valid.to_dict()
                raw[field] = value
                with self.assertRaises(ValueError):
                    HostProvenanceAttestation.from_dict(raw)

    def test_path_and_included_untracked_guards_apply_to_constructors_and_loaders(self):
        locator = self._locator
        unsafe_paths = (
            "/absolute", "\\\\host\\share", "a\\b", "a//b", "../a",
            "a/../b", "scheme:a", "a\x00b",
        )
        for path in unsafe_paths:
            with self.assertRaises(ValueError):
                ImmutableArtifactLocator(path, "a" * 64)
            with self.assertRaises(ValueError):
                ImmutableArtifactLocator.from_dict({"path": path, "sha256": "a" * 64})

        invocation, _, _, _ = self._records()
        for included in ("src/a", ["src/a", "src/a"], ["../a"], [1]):
            args = [
                locator("bundle"), locator("request"),
                {"run_id": "run", "stage_id": "stage"},
                {"run_id": "run", "operation_id": "operation"},
                locator("scope"), "base", "head", "final", included,
                locator("fingerprint"),
            ]
            with self.assertRaises(ValueError):
                ReviewInvocation(*args)
            raw = invocation.to_dict()
            raw["included_untracked"] = included
            with self.assertRaises(ValueError):
                ReviewInvocation.from_dict(raw)

    def test_identity_and_digest_guards_apply_to_constructors_and_loaders(self):
        invocation, reviewer_return, attestation, _ = self._records()
        with self.assertRaises(ValueError):
            ReviewInvocation(
                invocation.retained_bundle, invocation.request,
                invocation.attempt, {"run_id": "other", "operation_id": "operation"},
                invocation.scope, invocation.base, invocation.head,
                invocation.purpose, invocation.included_untracked,
                invocation.pre_dispatch_fingerprint,
            )
        raw = invocation.to_dict()
        raw["operation"]["run_id"] = "other"
        with self.assertRaises(ValueError):
            ReviewInvocation.from_dict(raw)

        target = dict(reviewer_return.target)
        target["run_id"] = "other"
        with self.assertRaises(ValueError):
            ReviewerReturn(
                reviewer_return.invocation, reviewer_return.operation,
                reviewer_return.request, target, reviewer_return.fingerprint,
                reviewer_return.report, reviewer_return.report_digest,
                reviewer_return.decision,
            )
        raw = reviewer_return.to_dict()
        raw["target"]["run_id"] = "other"
        with self.assertRaises(ValueError):
            ReviewerReturn.from_dict(raw)

        target = dict(reviewer_return.target)
        target["operation_id"] = "other"
        with self.assertRaises(ValueError):
            ReviewerReturn(
                reviewer_return.invocation, reviewer_return.operation,
                reviewer_return.request, target, reviewer_return.fingerprint,
                reviewer_return.report, reviewer_return.report_digest,
                reviewer_return.decision,
            )
        raw = reviewer_return.to_dict()
        raw["target"]["operation_id"] = "other"
        with self.assertRaises(ValueError):
            ReviewerReturn.from_dict(raw)

        with self.assertRaises(ValueError):
            ReviewerReturn(
                reviewer_return.invocation, reviewer_return.operation,
                reviewer_return.request, reviewer_return.target,
                reviewer_return.fingerprint, reviewer_return.report,
                "b" * 64, reviewer_return.decision,
            )
        raw = reviewer_return.to_dict()
        raw["report_digest"] = "b" * 64
        with self.assertRaises(ValueError):
            ReviewerReturn.from_dict(raw)
        with self.assertRaises(ValueError):
            HostProvenanceAttestation(
                attestation.reviewer_return, "b" * 64,
                attestation.execution_identity, attestation.execution_context,
                attestation.dispatch_facts,
            )
        raw = attestation.to_dict()
        raw["reviewer_return_digest"] = "b" * 64
        with self.assertRaises(ValueError):
            HostProvenanceAttestation.from_dict(raw)

    def test_host_values_require_exact_scalars_and_are_recursively_copied(self):
        class StringAlias(str):
            pass

        class IntAlias(int):
            pass

        class FloatAlias(float):
            pass

        locator = self._locator()
        for bad in (StringAlias("host"), IntAlias(1), FloatAlias(1.0)):
            with self.assertRaises(ValueError):
                HostProvenanceAttestation(locator, "a" * 64, bad, {}, {})
            raw = HostProvenanceAttestation(
                locator, "a" * 64, {"valid": True}, {}, {}
            ).to_dict()
            raw["execution_identity"] = bad
            with self.assertRaises(ValueError):
                HostProvenanceAttestation.from_dict(raw)
        identity = {"nested": ["value", {"key": "value"}]}
        context = {"context": ["value"]}
        facts = {"facts": {"enabled": True}}
        attestation = HostProvenanceAttestation(locator, "a" * 64, identity, context, facts)
        identity["nested"].append("changed")
        context["context"][0] = "changed"
        facts["facts"]["enabled"] = False
        self.assertEqual(attestation.execution_identity["nested"], ("value", {"key": "value"}))
        self.assertEqual(attestation.execution_context, {"context": ("value",)})
        self.assertEqual(attestation.dispatch_facts, {"facts": {"enabled": True}})
        with self.assertRaises(TypeError):
            attestation.execution_context["context"] = ()


if __name__ == "__main__":
    unittest.main()
