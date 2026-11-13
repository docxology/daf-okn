#!/usr/bin/env bash
# Offline package gate: the CI lint job's ruff and mypy, then pytest and coverage.
set -euo pipefail
# Keep the declared profile fixed even in a developer shell with pytest defaults.
unset PYTEST_ADDOPTS
if [ "$#" -ne 0 ]; then
    printf 'usage: bash scripts/gate.sh (no test-selection overrides)\n' >&2
    exit 2
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
uv run --locked --extra dev ruff check .
uv run --locked --extra dev mypy -p daf_okn
exec uv run --locked --extra dev python -m pytest tests/ --cov=src --cov-branch --cov-fail-under=90
