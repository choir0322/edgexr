#!/usr/bin/env bash
# Confirm that the learning-first starter structure is present. Safe to re-run.
# Inputs: no arguments; run from the repository root. Reads files and Git only.
# Outputs: a layout/status explanation. Exit 1 if a required file is missing.
# Fail promptly instead of concealing errors or unintended unset variables.
set -euo pipefail

# Keep the original required layout; this refactor does not change the check policy.
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

# Verify each named document without creating a missing placeholder silently.
for path in "${required[@]}"; do
  # A directory with the same name is not a valid replacement for a required file.
  if [[ ! -f "$path" ]]; then
    # Use stderr for the actionable failure explanation.
    echo "Missing required project file: $path" >&2
    # Report failure to the invoking shell or automation.
    exit 1
  fi
done

# Only report success once every required path has been checked.
echo "EdgeXR starter structure is complete."
# Git status is informative; the script does not initialize or modify a repository.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  # Read the branch name rather than assuming the default branch is main.
  echo "Git branch: $(git branch --show-current)"
else
  # A scaffold can still be inspected before Git initialization.
  echo "Git has not been initialized yet."
fi
