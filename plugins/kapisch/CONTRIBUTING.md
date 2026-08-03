# Contributing

Keep KAPISCH portable and small. Do not add a daemon, database, MCP service,
container runtime, hidden scheduler, or semantic approval engine.

Changes to durable evidence must include fixtures and tests. The validator is
read-only structural verification, not a semantic router or artifact writer.
From `plugins/kapisch`, run
`python -m unittest discover -s tests/kapisch_validation` and validate the
plugin manifest before proposing a change. From the repository root, also run
`python -m unittest discover -s tests` to validate the marketplace catalog and
its canonical plugin source.
