# Implementation plan (proposed)

1. Remove archived records older than 30 days using the global `archived=true` selector.
2. Add the ownership check after deletion to report whether the caller was authorized.
3. Verify with a test that an authorized owner can archive one record.
