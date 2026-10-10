# Group comments by task

## Purpose / big picture

Replace repetitive line-by-line commentary with short explanations above cohesive
tasks. A reader should see what each group achieves, why it exists, and any
important data shape, unit, timing or ownership constraint without reading a
comment before every statement. Preserve executable behavior and function contracts.

## Context and orientation

Target: `/Users/ryanchoi/Desktop/edgexr`, following the learning refactor at
`0b136e8`. The working tree was clean at initial inspection on 2026-10-10.
Scope includes all first-party Python source and tests, the Python documentation
checker, browser JavaScript/HTML/CSS and shell helpers. Inspect other tracked code
for the same convention; exclude vendor packages, model files and recordings.
Keep existing function docstrings, parameter/return annotations and JSDoc contracts.

## Progress

- [x] 2026-10-10: inspect repository instructions, working tree and representative comments.
- [x] 2026-10-10: prepare this reviewable plan before changing implementation files.
- [x] 2026-10-10: user reviewed the plan and confirmed proceeding.
- [x] 2026-10-10: review all 31 tracked code files (28 Python files, two shell
  scripts and one browser page); group comments throughout substantive code.
  Six package initializers have only module descriptions and need no change.
- [x] 2026-10-10: update the comment convention, study index and standing agent
  instructions. Diagram reviewed; unchanged because data flow, signatures,
  units, clocks, scheduling and executable behavior are unchanged. The three
  pipeline guides retain their named-function references; all 61 learning/diagram
  file links resolve.
- [x] 2026-10-10: exact AST and executable-token comparison passes for all 28
  Python files, preserving docstrings and types. Python comment tokens decrease
  from 1,840 to 342; these counts document the change, not a future quota.
- [x] 2026-10-10: shell executable lines and browser executable lines, JSDoc,
  HTML structure/text and CSS values match. Synthetic browser comparisons pass
  for 16 render cases and two polling cases.
- [x] 2026-10-10: snapshot checks run 48 tests: 46 pass, two skip (OpenCV absent,
  sandbox socket restriction). Contract audit covers 170 functions; shell syntax
  and layout checks pass. Baseline on Desktop: 47 pass, one OpenCV skip.
- [x] 2026-10-10: apply the tested patch to Desktop. Final Desktop checks:
  48 tests run, 47 pass, one skip (OpenCV unavailable); contract audit, shell
  syntax, project layout and Git whitespace checks pass. No commit or push.

## Plan of work

1. Capture a baseline and inventory all tracked first-party executable files.
2. Review each function and group adjacent statements by responsibility. Examples:
   command-line setup and parsing; input validation; worker initialization;
   reading a frame; preparing model input; running inference; publishing state;
   calculating freshness; rendering a result; shutdown and resource cleanup.
3. Replace comments that merely narrate syntax with one useful group explanation.
   Use blank lines to separate tasks where appropriate. Do not change variable
   names, control flow, strings, settings, function signatures or imports.
4. Retain narrowly placed explanations when a particular operation needs them:
   unit conversion, timestamp origin, lock scope, deliberate frame skipping,
   bounds, numerical conventions or a non-obvious limitation. Avoid repeating
   a function docstring in a comment for a very short function.
5. In tests, explain setup, action and expected behavior as groups rather than
   commenting every assignment and assertion. In browser code, group related
   rendering and polling work. In shell helpers, group each reporting/checking task.
6. Update `docs/learning/CODE_CONVENTIONS.md` and any current instruction that
   requests per-statement comments. Preserve historical records of the earlier
   refactor, with a note where needed that the newer convention supersedes it.
7. Review `docs/PIPELINE.md` and all three pipeline guides. The diagram should
   remain unchanged because this pass changes no data flow; record that explicitly.

## Concrete steps

Use a writable snapshot if Desktop writes require scoped approval. Apply only
the reviewed comment/documentation changes, preserving any intervening user edits.
Use syntax-aware checks to compare before/after executable content; do not strip
comment-looking text out of string literals. Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 scripts/check_learning_contracts.py
bash -n scripts/check_project.sh scripts/hardware_inventory.sh
bash scripts/check_project.sh
git diff --check
```

## Validation and acceptance

- Every first-party code file has been reviewed, including tests and scripts.
- Comments describe meaningful task groups, not every individual statement.
- Important explanations of units, shapes, concurrency and freshness remain.
- Python ASTs match exactly, including function docstrings and annotations.
- JavaScript executable tokens and shell commands are unchanged; CSS values and
  HTML structure are unchanged. Check documentation links after edits.
- All runnable tests pass; report environment-dependent skips explicitly.
- No model downloads, new dependencies, camera changes or benchmark changes.
- No Pi performance claim is needed for a verified comment-only change.

## Surprises and discoveries

The previous refactor added repetitive comments even to individual imports,
argument declarations, assignments and return statements. These obscure the
larger tasks. The documentation checker concerns function contracts, which remain
useful and should not be removed with the line-by-line comments.

## Decision log

- 2026-10-10: group by semantic responsibility, not a fixed number of lines.
- 2026-10-10: preserve docstrings/types and all executable statements; this is
  a comment-style change, not another implementation refactor.
- 2026-10-10: short self-explanatory helpers may need only their existing docstring;
  do not replace redundant line comments with redundant group comments.

## Outcomes and retrospective

The approved comment-style change is complete and locally verified. Comments
now explain cohesive work rather than narrating assignments and calls. CLI
parsing, acquisition, numerical processing, publication, rendering and cleanup
have explicit boundaries. Small self-explanatory helpers rely on their retained
docstrings. No third-party code, model, dependency or benchmark protocol changed.

Changes are ready for review, not automatically committed or pushed. This pass
does not resolve the separate Pi smoke-check milestone from the original typed
refactor. A hardware run was not performed for these comment-only edits.
