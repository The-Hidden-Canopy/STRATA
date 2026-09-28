# Contributing to Bundle

Contributions should preserve the local-first boundary: the core must remain
usable without a Hidden Canopy account, hosted service, mandatory network
connection, or mandatory telemetry.

Before opening a pull request:

1. Add or update tests for behavior changes.
2. Run `python -m unittest discover -s tests -v`.
3. Run `python -m compileall -q bundle`.
4. Document schema or public API changes.
5. Include provenance and license notices for adapted code.

By submitting a contribution, you agree that it may be distributed under the
repository's Apache-2.0 license. Bundle welcomes DCO sign-off in commit
messages (`Signed-off-by: Name <email>`).
