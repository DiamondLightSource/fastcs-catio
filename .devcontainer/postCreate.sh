#!/usr/bin/env bash
# postCreate: run the claude-sandbox installer baked in by
# 'just promote'. Idempotent so devcontainer rebuilds re-establish
# the shadow without re-downloading Claude.
set -euo pipefail

# Install Python dependencies and pre-commit hooks. `uv venv --clear` wipes
# the venv that lives in /cache (a persistent named volume), so any bash
# hash entries pointing into the old venv (e.g. cached `pre-commit` path)
# are stale. `hash -r` after `uv sync` forces re-resolution against the
# freshly populated venv and against any new `uv` location after a base
# image bump.
uv venv --clear
hash -r
uv sync
pre-commit install --install-hooks

bash .devcontainer/claude-sandbox/install.sh
