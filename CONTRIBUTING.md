# Contributing

Please read `AGENTS.md`, `docs/PHASE_BUILDS.md` and the limitations in the README before opening a pull request. Keep changes narrow and backed by deterministic tests. New analyzers must distinguish confirmed errors from evidence that merely requires review. Never include private transaction credentials, wallet seeds, secrets, or personally identifiable financial records in test fixtures. Add unit, boundary, negative and regression tests, and document source links and data provenance. Reproduce checks locally with `PYTHONPATH=src python -m unittest discover -s tests -v`.
