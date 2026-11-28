# Proof obligations and evidence quality

**Load when:** the target makes material correctness, coverage, implementation, acceptance, security, or safety claims, or when tests/observations are offered as proof.

**Retrieve:** exact claim and governing obligation; source revision/environment; test scope, assertions, and results; negative scenarios; relevant observed behavior; and known omissions.

**Check:** unsupported claims; missing evidence; conclusions exceeding test/observation scope; tests that do not establish the claimed guarantee; missing negative cases; and confusion among proposed, implemented, verified, and accepted. Confirm that evidence belongs to the reviewed revision and that success-path tests do not stand in for authorization, isolation, failure, or unrelated-data invariants.

**Report:** tie each finding to the exact claim and evidence. State what was verified, what was not, and the missing proof/test or counterexample. For an evidence gap, report what cannot be verified; do not promote a possible defect to an established one.
