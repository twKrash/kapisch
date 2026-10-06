import unittest
from collections.abc import Mapping
from dataclasses import replace

from kapisch_core.review import (
    EvidenceLocator,
    HostProvenanceAttestation,
    ImmutableArtifactLocator,
    ReviewerReturn,
    ReviewInvocation,
    ReviewResult,
)


class AuthoritativeItemsMapping(Mapping):
    """Expose only items(); every other mapping view is adversarial."""

    def __init__(self, pairs):
        self._pairs = tuple(pairs)
        self.calls = 0

    def items(self):
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("mapping was consumed more than once")
        pairs = self._pairs
        self._pairs = (("wrong", "view"),)
        return pairs

    def __getitem__(self, key):
        raise AssertionError("mapping indexing is not authoritative")

    def __iter__(self):
        raise AssertionError("mapping iteration is not authoritative")

    def __len__(self):
        raise AssertionError("mapping length is not authoritative")


class ReviewFormatTests(unittest.TestCase):
    def _locator(self, path="artifact.json"):
        return ImmutableArtifactLocator(path, "a" * 64)

    def _records(self):
        locator = self._locator
        invocation = ReviewInvocation(
            locator("bundle"), locator("request"),
            {"run_id": "run", "stage_id": "stage"},
            {"run_id": "run", "operation_id": "operation"},
            locator("scope"), "base", "head", "final", ["7372632f61"],
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

    def test_locator_boundary_rejects_stateful_subclasses_and_accepts_evidence(self):
        class StatefulLocator(ImmutableArtifactLocator):
            def __getattribute__(self, name):
                if name in {"path", "sha256"}:
                    try:
                        reads = object.__getattribute__(self, "_reads")
                    except AttributeError:
                        return super().__getattribute__(name)
                    reads[name] = reads.get(name, 0) + 1
                    if reads[name] > 1:
                        return "injected" if name == "path" else "b" * 64
                return super().__getattribute__(name)

        locator = StatefulLocator("safe", "a" * 64)
        object.__setattr__(locator, "_reads", {})
        invocation, _, _, _ = self._records()
        with self.assertRaises(ValueError):
            locator.canonical_bytes()
        with self.assertRaises(ValueError):
            locator.to_dict()
        with self.assertRaises(ValueError):
            ReviewInvocation(
                locator, invocation.request, invocation.attempt,
                invocation.operation, invocation.scope, invocation.base,
                invocation.head, invocation.purpose,
                invocation.included_untracked, invocation.pre_dispatch_fingerprint,
            )

        evidence = EvidenceLocator("safe", "a" * 64)
        self.assertEqual(evidence.canonical_bytes(), self._locator("safe").canonical_bytes())
        self.assertEqual(evidence.to_dict(), {"path": "safe", "sha256": "a" * 64})

    def test_mapping_inputs_are_snapshotted_once_from_authoritative_items(self):
        attempt = AuthoritativeItemsMapping(
            (("run_id", "run"), ("stage_id", "stage"))
        )
        invocation, _, _, _ = self._records()
        record = ReviewInvocation(
            invocation.retained_bundle, invocation.request, attempt,
            invocation.operation, invocation.scope, invocation.base,
            invocation.head, invocation.purpose, invocation.included_untracked,
            invocation.pre_dispatch_fingerprint,
        )
        self.assertEqual(attempt.calls, 1)
        self.assertEqual(record.attempt["stage_id"], "stage")

    def test_record_load_and_locator_loaders_use_authoritative_items(self):
        invocation, _, _, _ = self._records()
        raw = AuthoritativeItemsMapping(tuple(invocation.to_dict().items()))
        restored = ReviewInvocation.from_dict(raw)
        self.assertEqual(restored.canonical_bytes(), invocation.canonical_bytes())
        locator = AuthoritativeItemsMapping(
            (("path", "safe"), ("sha256", "a" * 64))
        )
        self.assertEqual(ImmutableArtifactLocator.from_dict(locator).path, "safe")
        self.assertEqual(raw.calls, 1)
        self.assertEqual(locator.calls, 1)

    def test_closed_identity_mappings_and_nested_host_facts_use_snapshot(self):
        invocation, reviewer_return, _, _ = self._records()
        attempt = AuthoritativeItemsMapping(
            (("run_id", "run"), ("stage_id", "stage"))
        )
        operation = AuthoritativeItemsMapping(
            (("run_id", "run"), ("operation_id", "operation"))
        )
        record = ReviewInvocation(
            invocation.retained_bundle, invocation.request, attempt,
            operation, invocation.scope, invocation.base, invocation.head,
            invocation.purpose, invocation.included_untracked,
            invocation.pre_dispatch_fingerprint,
        )
        self.assertEqual(record.operation["operation_id"], "operation")
        identity = AuthoritativeItemsMapping((("host", "one"),))
        HostProvenanceAttestation(self._locator(), "a" * 64, identity, {}, {})
        self.assertEqual(identity.calls, 1)
        target = AuthoritativeItemsMapping(
            (("run_id", "run"), ("stage_id", "stage"),
             ("operation_id", "operation"), ("base", "base"), ("head", "head"))
        )
        returned = ReviewerReturn(
            reviewer_return.invocation,
            AuthoritativeItemsMapping(
                (("run_id", "run"), ("operation_id", "operation"))
            ),
            reviewer_return.request, target, reviewer_return.fingerprint,
            reviewer_return.report, reviewer_return.report_digest,
            reviewer_return.decision,
        )
        self.assertEqual(returned.target["head"], "head")
        self.assertEqual(target.calls, 1)

    def test_adversarial_snapshot_keys_are_rejected_by_constructors_and_loaders(self):
        class StringAlias(str):
            pass

        class MappingAlias:
            def __hash__(self):
                return hash("path")

            def __eq__(self, other):
                return other == "path"

        invocation, _, _, _ = self._records()
        valid_locator = (("path", "safe"), ("sha256", "a" * 64))
        locator_cases = (
            valid_locator + (("path", "other"),),
            ((StringAlias("path"), "safe"), ("sha256", "a" * 64)),
            ((MappingAlias(), "safe"), ("sha256", "a" * 64)),
            (("path", "safe"), ("sha256", "a" * 64), (chr(0xD800), "x")),
        )
        for pairs in locator_cases:
            with self.assertRaises(ValueError):
                ImmutableArtifactLocator.from_dict(AuthoritativeItemsMapping(pairs))

        raw = invocation.to_dict()
        for key in (StringAlias("base"), MappingAlias(), chr(0xD800)):
            candidate = AuthoritativeItemsMapping(
                tuple(raw.items()) + ((key, raw["base"]),)
            )
            with self.assertRaises(ValueError):
                ReviewInvocation.from_dict(candidate)

        locator = self._locator()
        for pairs in (
            (("fact", True), ("fact", False)),
            ((StringAlias("fact"), True),),
            ((MappingAlias(), True),),
            ((chr(0xD800), True),),
        ):
            nested = AuthoritativeItemsMapping(pairs)
            with self.assertRaises(ValueError):
                HostProvenanceAttestation(locator, "a" * 64, nested, {}, {})
            loaded = HostProvenanceAttestation(locator, "a" * 64, {}, {}, {}).to_dict()
            loaded["execution_identity"] = AuthoritativeItemsMapping(pairs)
            with self.assertRaises(ValueError):
                HostProvenanceAttestation.from_dict(loaded)

    def test_duplicate_identity_keys_are_rejected_by_mapping_constructors_and_loaders(self):
        invocation, reviewer_return, _, result = self._records()
        cases = (
            (
                lambda pairs: ReviewInvocation(
                    invocation.retained_bundle, invocation.request, pairs,
                    invocation.operation, invocation.scope, invocation.base,
                    invocation.head, invocation.purpose,
                    invocation.included_untracked,
                    invocation.pre_dispatch_fingerprint,
                ),
                lambda pairs: ReviewInvocation.from_dict({
                    **invocation.to_dict(), "attempt": pairs,
                }),
                (('run_id', 'run'), ('run_id', 'other'), ('stage_id', 'stage')),
            ),
            (
                lambda pairs: ReviewerReturn(
                    reviewer_return.invocation, pairs, reviewer_return.request,
                    reviewer_return.target, reviewer_return.fingerprint,
                    reviewer_return.report, reviewer_return.report_digest,
                    reviewer_return.decision,
                ),
                lambda pairs: ReviewerReturn.from_dict({
                    **reviewer_return.to_dict(), "operation": pairs,
                }),
                (('run_id', 'run'), ('run_id', 'other'),
                 ('operation_id', 'operation')),
            ),
            (
                lambda pairs: ReviewResult(
                    result.invocation, result.request, pairs, result.scope,
                    result.fingerprint, result.reviewer_return, result.post_result,
                    result.provenance,
                ),
                lambda pairs: ReviewResult.from_dict({
                    **result.to_dict(), "target": pairs,
                }),
                (('run_id', 'run'), ('run_id', 'other'),
                 ('stage_id', 'stage'), ('operation_id', 'operation'),
                 ('base', 'base'), ('head', 'head')),
            ),
        )
        for construct, load, pairs in cases:
            with self.assertRaises(ValueError):
                construct(AuthoritativeItemsMapping(pairs))
            with self.assertRaises(ValueError):
                load(AuthoritativeItemsMapping(pairs))

    def test_duplicate_outer_record_fields_are_rejected_by_record_loader(self):
        invocation, _, _, _ = self._records()
        raw = tuple(invocation.to_dict().items()) + (
            ('base', invocation.base),
        )
        with self.assertRaises(ValueError):
            ReviewInvocation.from_dict(AuthoritativeItemsMapping(raw))

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
        for purpose in ("approve", "ready", "unknown"):
            with self.subTest(purpose=purpose):
                arguments = {
                    name: getattr(invocation, name)
                    for name in invocation.__dataclass_fields__
                }
                arguments["purpose"] = purpose
                with self.assertRaises(ValueError):
                    ReviewInvocation(**arguments)
                raw = invocation.to_dict()
                raw["purpose"] = purpose
                with self.assertRaises(ValueError):
                    ReviewInvocation.from_dict(raw)
        for decision in ("approve", "ready", "unknown"):
            with self.subTest(decision=decision):
                arguments = {
                    name: getattr(reviewer_return, name)
                    for name in reviewer_return.__dataclass_fields__
                }
                arguments["decision"] = decision
                with self.assertRaises(ValueError):
                    ReviewerReturn(**arguments)
                raw = reviewer_return.to_dict()
                raw["decision"] = decision
                with self.assertRaises(ValueError):
                    ReviewerReturn.from_dict(raw)

    def test_supported_purposes_and_decisions_round_trip(self):
        invocation, reviewer_return, _, _ = self._records()
        for purpose in ("iteration", "final"):
            with self.subTest(purpose=purpose):
                candidate = replace(invocation, purpose=purpose)
                restored = ReviewInvocation.from_dict(candidate.to_dict())
                self.assertEqual(restored.purpose, purpose)
        for decision in ("clear", "findings", "inconclusive"):
            with self.subTest(decision=decision):
                candidate = replace(reviewer_return, decision=decision)
                restored = ReviewerReturn.from_dict(candidate.to_dict())
                self.assertEqual(restored.decision, decision)

    def test_sha256_validation_covers_all_locator_and_digest_fields(self):
        class DigestAlias(str):
            pass

        malformed = (
            "A" * 64,
            "a" * 63,
            "g" * 64,
            "a" * 64 + "\n",
            1,
            DigestAlias("a" * 64),
        )
        for value in malformed:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    ImmutableArtifactLocator("artifact.json", value)
                with self.assertRaises(ValueError):
                    ImmutableArtifactLocator.from_dict({
                        "path": "artifact.json", "sha256": value,
                    })
                with self.assertRaises(ValueError):
                    EvidenceLocator("artifact.json", value)
                with self.assertRaises(ValueError):
                    EvidenceLocator.from_dict({
                        "path": "artifact.json", "sha256": value,
                    })

        invocation, reviewer_return, attestation, _ = self._records()
        for value in malformed:
            with self.subTest(field="report_digest", value=repr(value)):
                arguments = {
                    name: getattr(reviewer_return, name)
                    for name in reviewer_return.__dataclass_fields__
                }
                arguments["report_digest"] = value
                with self.assertRaises(ValueError):
                    ReviewerReturn(**arguments)
                raw = reviewer_return.to_dict()
                raw["report_digest"] = value
                with self.assertRaises(ValueError):
                    ReviewerReturn.from_dict(raw)
            with self.subTest(field="reviewer_return_digest", value=repr(value)):
                arguments = {
                    name: getattr(attestation, name)
                    for name in attestation.__dataclass_fields__
                }
                arguments["reviewer_return_digest"] = value
                with self.assertRaises(ValueError):
                    HostProvenanceAttestation(**arguments)
                raw = attestation.to_dict()
                raw["reviewer_return_digest"] = value
                with self.assertRaises(ValueError):
                    HostProvenanceAttestation.from_dict(raw)

        locator_fields = {
            "ReviewInvocation": (
                "retained_bundle", "request", "scope", "pre_dispatch_fingerprint",
            ),
            "ReviewerReturn": ("invocation", "request", "fingerprint", "report"),
            "HostProvenanceAttestation": ("reviewer_return",),
            "ReviewResult": (
                "invocation", "request", "scope", "fingerprint",
                "reviewer_return", "post_result", "provenance",
            ),
        }
        for record in self._records():
            for field in locator_fields[type(record).__name__]:
                raw = record.to_dict()
                for value in malformed:
                    with self.subTest(field=f"{type(record).__name__}.{field}", value=repr(value)):
                        raw[field]["sha256"] = value
                        with self.assertRaises(ValueError):
                            type(record).from_dict(raw)
                        raw[field]["sha256"] = "a" * 64

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
        invalid_encoded_paths = [["00"], ["2f61"], ["2e"], ["2e2e2f61"], ["612f2f62"]]
        for included in (
            "src/a", ["7372632f61", "7372632f61"], ["../a"], [1],
            *invalid_encoded_paths,
        ):
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

        valid = list(self._records()[0].to_dict()["included_untracked"])
        valid.append("7261772dff0a")
        args[8] = valid
        self.assertEqual(ReviewInvocation(*args).included_untracked[-1], "7261772dff0a")
        raw = invocation.to_dict()
        raw["included_untracked"] = valid
        self.assertEqual(
            ReviewInvocation.from_dict(raw).included_untracked[-1], "7261772dff0a"
        )
        for malformed in ("", "0", "GG", "7372632F61", "7372632f6"):
            args[8] = [malformed]
            with self.assertRaises(ValueError):
                ReviewInvocation(*args)
            raw["included_untracked"] = [malformed]
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
