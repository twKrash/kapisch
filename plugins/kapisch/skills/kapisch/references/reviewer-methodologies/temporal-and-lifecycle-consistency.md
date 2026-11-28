# Temporal and lifecycle consistency

**Load when:** claims depend on version, date, status, ordering, supersession, state transition, recovery, retry, or continuation.

**Retrieve:** current revision/state, relevant history and dates, lifecycle definitions, superseding decisions, producer/consumer sequence, and recovery/continuation evidence.

**Check:** stale assumptions or documents; invalid sequencing or lifecycle transitions; superseded decisions presented as current; status claims inconsistent with current or historical evidence; and unsupported retry, interruption, recovery, or continuation assumptions. Verify that a claimed historical artifact is not silently treated under new semantics.

**Report:** cite current and historical evidence and identify which claim is current, stale, ambiguous, or unverified. State temporal/dependency consequences only when supported by the lifecycle.
