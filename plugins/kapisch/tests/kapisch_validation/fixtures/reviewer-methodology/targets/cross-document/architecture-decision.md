# Architecture decision (accepted 2026-11-22)

A daily sweeper deletes all rows for disabled tenants, without an owner request. The query uses the tenant ID in its selector.
