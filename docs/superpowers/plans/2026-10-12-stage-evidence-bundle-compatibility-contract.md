# Stage 4.0 `stage-evidence/1` bundle-compatibility contract

**Status: DRAFT — PENDING INDEPENDENT REVIEW AND OWNER APPROVAL.** This
document proposes the separate retained-bundle capability prerequisite
referenced by architecture design §32.1, §32.2, and §32.6. It does not
approve or implement Stage 4.0.

## 1. Purpose and boundary

Architecture design §32 requires an attempt's exact retained bundle to
explicitly support `stage-evidence/1`; otherwise that attempt is ineligible.
It assigns definition of that capability to a separate bundle-compatibility
dependency and deliberately leaves that dependency undefined. This contract
fills only that gap. It does not amend, restate, relax, or implement any
Stage 4 requirement.

The capability describes an explicit declaration by one exact, already
retained CoreBundle. It is neither a statement about the current distribution
bundle nor an inference from protocol version, schema contents, role,
operation, consumer, or other capability. The retained bundle digest
continues to identify SHA-256 of the exact canonical bundle bytes.

## 2. Exact declaration

A new-format CoreBundle declares this capability with one top-level field:

```json
"stage_evidence_contract": "stage-evidence/1"
```

`stage_evidence_contract` is a separate declaration, not an extension or
reinterpretation of `authority_contract`. Its JSON type is string, and its
only supported value is the exact, case-sensitive string `stage-evidence/1`.
The field is part of the payload covered by canonical JSON encoding and the
bundle SHA-256 digest.

CoreBundle canonicalization uses sorted JSON object keys. Thus the field's
canonical position is determined by that rule: among the top-level keys it
sorts after `review_schema_variant` and before `vocabulary` (or after the
preceding key when optional review fields are absent). No hand-maintained
insertion order or alternative encoding is introduced.

The declaration is independent of the existing optional review capability
pair. A new-format bundle may contain the stage-evidence declaration with or
without the complete existing pair `review_contract` and
`review_schema_variant`; those fields retain their existing joint-presence
and exact-value rules. This does not imply that stage-evidence support implies
review support, or vice versa.

## 3. Testable support predicate and fail-closed behavior

For a CoreBundle that passes `verify_bundle` and the supported retained
identity-schema validation, `supports_stage_evidence(bundle)` returns true if
and only if `bundle.payload["stage_evidence_contract"] == "stage-evidence/1"`.
The accessor must enforce or require that complete validation before returning
true; a canonical digest-valid bundle with an unsupported schema fingerprint
is not eligible. All other states return false or fail validation as follows:

- Missing declaration: bundle may remain valid for its previously supported
  operations, but predicate returns false.
- A known but unsupported string value: verification rejects the bundle; it
  cannot be used as a retained bundle for any consumer requiring this
  declaration.
- Wrong JSON type, null, malformed value, or partial/alternate spelling:
  verification rejects the bundle; no coercion or normalization occurs.
- Unknown top-level declaration/capability field: verification rejects the
  bundle as it does other unknown top-level fields. No unknown capability is
  ignored or treated as an alias.
- Digest mismatch, noncanonical bytes, duplicate keys, or any other existing
  verification failure continues to reject the bundle before capability use.

No consumer may inspect the raw mapping and implement its own capability
interpretation. `verify_bundle` validates the declaration's closed shape and
value; `_validation_schema.py` validates the exact supported identity-schema
fingerprint; `supports_stage_evidence` is the sole reader/accessor for the
semantic predicate. The accessor accepts only a fully validated retained
`CoreBundle` and does not repair or downgrade invalid input.

Stage 4's §32.2 predicate may rely on the exact attempt's validated retained
bundle plus this accessor returning true. It must not substitute an installed
bundle, infer support from schema shape or protocol version, or rewrite
retained bytes. §32's separately required applicable Stage 6.5 capabilities
remain separately checked by their own approved contracts; this declaration
does not imply or duplicate them.

## 4. Retained and legacy compatibility

Under the updated implementation, existing legacy-format bundles continue
to verify exactly under their existing legacy field and schema-set rules.
Existing new-format bundles declaring only
`authority_contract = "global-authority/1"` likewise continue to verify with
exactly their current meaning and eligibility for existing operations. Existing
review-capability bundles preserve their current rules. None is reinterpreted
as declaring `stage-evidence/1`, regardless of schema content or protocol
version.

Adding support creates a new canonical bundle variant with a new recognized
embedded-schema fingerprint. It does not mutate, upgrade, migrate, or replace
any retained bundle. Old bytes retain their original digest and historical
interpretation. Updated readers accept those prior variants under their
existing fingerprint mappings. Older readers that do not recognize the new
fingerprint may reject new bundle bytes; forward compatibility with older
implementations is not promised. A retained bundle without the new declaration
remains usable under updated readers for operations it already supports, but
is ineligible wherever §32 requires explicit stage-evidence support.

## 5. Scope limits

This contract defines one capability only. It does not define a general
capability registry, negotiation protocol, capability inheritance, aliases,
version ranges, forward compatibility for unknown declarations, future
capability values, or migration of retained bundles. Its only schema changes
are the optional exact CoreBundle declaration and recognition of the resulting
exact embedded-schema fingerprint described in §6. It does not define or
modify Stage 4 evidence structure, eligibility beyond the explicit bundle
check, reservation production, Stage 6.5 behavior, or any other §32 invariant.

## 6. Implementation plan — pending approval

No production changes are authorized by this document. After independent
review and explicit owner approval, a narrowly scoped implementation should
change these seams:

1. `core/kapisch_core/bundle.py` (`compile_bundle`) adds the exact top-level
   declaration to newly compiled canonical bundles. This is the source
   producer and preserves the existing `authority_contract` value.
2. `core/schemas/v3/bundle.json` adds an optional `stage_evidence_contract`
   property whose only accepted value is `stage-evidence/1`; it remains
   optional so pre-capability payloads retain their old shape. The compiler
   embeds this closed schema in newly compiled bundles.
3. `core/kapisch_core/bundle.py` (`verify_bundle`) accepts the new optional
   field only for the existing new schema set, validates its exact string
   value, and continues rejecting unknown/partial declarations. Legacy exact
   fields and current global-authority/review rules remain unchanged. Verify
   that newly compiled payloads validate against their embedded bundle schema.
4. `core/kapisch_core/_validation_schema.py` recognizes the exact identity
   fingerprints produced by the new embedded bundle schema. Preserve every
   existing fingerprint and its historical mapping. Map each new
   `global-authority/1` fingerprint to the same existing identity-schema
   variant as its predecessor, retaining the exact global-gate schema pairing.
   Do not weaken fingerprint validation, normalize historical schemas, or
   admit cross-generation hybrids.
5. Adjacent to `supports_review_evidence`, define and export the single
   `supports_stage_evidence(bundle)` accessor. It returns true only when the
   bundle has the exact declaration and its retained identity schema passes
   supported-fingerprint validation, following the existing review-accessor
   pattern; it does not duplicate declaration or fingerprint rules.
6. `tooling/build/build_bundle.py` is the existing canonical-copy producer.
   Run it after changing the compiler to refresh exactly its three outputs:
   `core/dist/core-bundle.json`,
   `core/kapisch_core/resources/core-bundle.json`, and
   `tests/conformance/fixtures/v3/bundle.json`. Do not rewrite legacy fixtures.
7. `tests/core/test_bundle.py` (existing bundle format and capability
   coverage) adds focused declaration, accessor, compatibility, and
   canonical-byte tests. `tests/core/test_storage.py` may add a retained exact-
   bundle assertion if needed to prove the accessor operates on the
   digest-verified retained object; no storage production change is expected.
8. The Stage 4 implementation, in a separate approved scope, calls the
   accessor at its §32.2 eligibility seam using the exact retained bundle. No
   Stage 4 call site changes in this capability implementation.

The capability changes only compilation, bundle-schema validation, exact
identity-fingerprint recognition, its accessor, generated canonical copies,
and focused tests. Bundle storage, SHA-256 calculation, canonical JSON
algorithm, legacy schema recognition, historical identity fingerprints,
old global-authority bundles, and existing consumers retain their behavior
under the updated implementation. New exact fingerprints map to existing
identity variants and their existing gate-schema pairings; no historical
schema is reinterpreted. Stage 4 may later rely on the approved accessor. No
Stage 4 source, Stage 4 artifact, or §32 implementation is part of this plan.

Required regressions before approval of implementation:

- **Independent combinations:** verify the four new-format combinations:
  neither optional capability, review pair only, stage-evidence only, and both.
  Stage-only support returns true while existing review support remains false;
  review-pair behavior remains unchanged. A partial or invalid review pair is
  rejected even when stage-evidence is declared.
- **Embedded schema and identity:** newly compiled payload validates against
  its embedded `bundle` schema and exact recognized identity fingerprint;
  existing fingerprints remain recognized with unchanged mappings. New
  fingerprints map only to their matching existing identity and global-gate
  schema variants; unsupported fingerprints and cross-generation hybrids fail.
  Newly compiled bundle identity validation succeeds and existing review
  support remains true.
- **State recovery:** public state publication and loading accept the new
  retained variant, including a fresh-process reload, while historical legacy,
  Stage 5.4/5.5, and review variants retain their original interpretation.
- **Unsupported:** a present but unsupported string declaration is rejected
  by verification and cannot yield eligibility.
- **Absent:** current valid legacy and new-format bundles without declaration
  retain verification and accessor returns false.
- **Malformed/unknown:** wrong type, malformed/alternate value, duplicate
  declaration key, and unknown capability field fail closed; no normalization.
- **Legacy retention:** historical legacy fixture and pre-capability
  global-authority bytes retain their old verification behavior and digest.
- **Digest/canonicalization stability:** canonical sorted-key encoding places
  the new key deterministically; the compiled bytes hash to the expected
  digest; verify rejects noncanonical bytes and altered digest; old retained
  bytes and their digest remain byte-identical.
- **Generated copies:** build `--check` proves all three new-format copies
  equal compiler output, while legacy conformance fixtures remain unchanged.

All implementation tests must preserve every §32 requirement and existing
bundle contract. The implementation plan itself is pending approval and does
not authorize production edits.

## 7. Approval gate and owner questions

Before implementation, owner approval is required for the exact field name
`stage_evidence_contract`, its standalone exact-string value, and its
independence from the review capability pair. Owner must also confirm that
verification should reject unknown declaration fields while a valid absent
field remains compatible but unsupported, as specified above. Any change to
these decisions requires updating this contract and obtaining fresh review
and approval; implementation must not choose among alternatives silently.
