# Cost-aware dispatch dogfood fixture

This is a post-implementation documentation fixture, not the active Change 2
graph. It neither dispatches agents nor schedules parallel work. IDs, assignments,
and evidence below are illustrative logical records only.

## Fixture nodes

| ID | Requested work | Logical assignment | Expected disposition |
| --- | --- | --- | --- |
| D01 | Remove two unused imports in named files; run the named formatter check. | `mechanical` / `mechanic` / `cheap` | Complete after exact scoped verification. |
| D02 | Add one fully specified display label and its named test assertion. | `prescriptive` / `implementer-lite` / `cheap` | Attempt `AT-D02-1` is persisted before work. |
| D03 | “Improve reminder delivery” with no acceptance criteria. | `design` / `architect` / `high` | Block for architect amendment and explicit approval. |
| D04 | Sort imports in `a.py` exactly as the formatter specifies. | `mechanical` / `mechanic` / `cheap` | Batch member `B01-1`. |
| D05 | Remove an unused import in `b.py`; run the same check. | `mechanical` / `mechanic` / `cheap` | Batch member `B01-2`. |
| D06 | Apply a fully specified household-authorization rule and its named tests. | `prescriptive` / `implementer` / `standard` | High risk promotes beyond implementer-lite and requires deep independent high-tier review. |

## Persisted assignment and escalation trace

Before work, each node records an assignment ID, source revision, selected
context references, scope fingerprint, and attempt ID. Resume reloads those
records and continues the same assignment. In this fixture D02 discovers a
documented compatibility boundary absent from its approved scope; one persisted
escalation `E-D02-1` records the changed scope/context and moves its replacement
attempt to `bounded` / `implementer` / `standard`. A repeat with identical
context and scope cannot escalate again.

## Sequential composite batch

`B01` contains ordered members `D04`, then `D05`, with each assignment ID,
member verification result, and composite verification result recorded. It runs
sequentially as one composite unit. If D04 succeeds and D05 fails, D04 evidence
is preserved but no downstream work unlocks unless an explicit member-level
dependency says otherwise.

## Resume and review expectations

An interruption after D02's first attempt resumes from its persisted assignment
and attempt evidence; it does not silently reclassify D02 or rerun completed
D01. D03 remains blocked until architect amendment/approval. D06 receives deep,
independent high-tier review and final readiness; implementation tier never
reduces review quality. The fixture contains no model IDs, token/cache/cost
claims, live agent execution, ready waves, or parallel scheduling.
