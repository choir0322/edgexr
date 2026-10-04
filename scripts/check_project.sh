#!/usr/bin/env bash
# Confirm that the learning-first starter structure is present. Safe to re-run.
set -euo pipefail

required=(
  "AGENTS.md"
  "README.md"
  ".agent/PLANS.md"
  "docs/PROJECT.md"
  "docs/ARCHITECTURE.md"
  "docs/HARDWARE.md"
  "docs/BENCHMARKING.md"
  "docs/ROADMAP.md"
)

for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing required project file: $path" >&2
    exit 1
  fi
done

echo "EdgeXR starter structure is complete."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Git branch: $(git branch --show-current)"
else
  echo "Git has not been initialized yet."
fi
