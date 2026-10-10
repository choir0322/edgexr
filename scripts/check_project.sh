#!/usr/bin/env bash
# Confirm that the learning-first starter structure is present. Safe to re-run.
# Inputs: no arguments; run from the repository root. Reads files and Git only.
# Outputs: a layout/status explanation. Exit 1 if a required file is missing.
set -euo pipefail

# Define the required documentation, then fail on the first missing file.
# This check reports problems; it does not create replacement placeholders.
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

# Report the successful layout check and current branch when Git is available.
# An uninitialized scaffold is still valid; this helper never initializes Git.
echo "EdgeXR starter structure is complete."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Git branch: $(git branch --show-current)"
else
  echo "Git has not been initialized yet."
fi
