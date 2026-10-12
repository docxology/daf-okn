# tests/analysis/ — agent contract

Behavior tests for `src/daf_okn/analysis/` (one-to-one
mirror per SUBMODULAR-CODE-2). Pure-domain tests only: no mocks, no
network; subprocess invocations target this project's own entrypoints.
Keep test files co-located with their subject module's subpackage; move a
test only when its subject module moves, via `git mv`.

## Files

- `README.md` — scope of this cluster.

## See Also

- [`../AGENTS.md`](../AGENTS.md) — shared testing contract.
- [`../../src/daf_okn/AGENTS.md`](../../src/daf_okn/AGENTS.md) — package-level module map covering `analysis/`.
