# EdgeXR learning refactor — implementation and verification

## Purpose / big picture

Make the entire first-party codebase readable as a course in the camera-motion,
object-detection and IMU pipelines without changing algorithms, defaults, public
commands, saved-file schemas, hardware access or benchmark protocols. Save the
live diagram in Git and keep it current as the implementation evolves.

## Context and orientation

Source inspected: Desktop repository at commit
`6a53d2769b33946ecf794ada3eff664c13653015` plus the user's uncommitted roadmap
and AP agenda. Preserve those changes. Approximately 2,600 lines span Python
source/tests, browser HTML/JavaScript and two shell scripts. Third-party FFmpeg,
OpenCV, NumPy, SunFounder packages and downloaded model internals are not ours to
refactor. Explain their boundaries and do not edit or vendor them.

Implementation was prepared and verified in a writable copy, then applied to
Desktop with scoped permission approval. No commits, pushes, model downloads
or hardware changes are implicit.

## Progress

- [x] 2026-10-08: inventory first-party code and read repository instructions.
- [x] 2026-10-08: initial baseline attempted; Desktop sandbox caused two test
  errors when tests created temporary recording directories. OpenCV and socket
  checks were skipped. Repeat in writable copy before judging regressions.
- [x] 2026-10-08: user confirmed the reviewed scope and authorized implementation.
- [x] 2026-10-08: save live diagram, standing maintenance rule and three source-linked guides.
- [x] 2026-10-08: writable-copy baseline: 48 tests run, 46 passed, 2 skipped
  (OpenCV unavailable, loopback bind restricted). No dependency installed.
- [x] 2026-10-08: refactor shared live plumbing and image-motion pipeline; update guide.
- [x] 2026-10-08: refactor saved/live object detection; update guide.
- [x] 2026-10-08: refactor baseline/rotation/live IMU; update guide.
- [x] 2026-10-08: refactor offline recording/analysis, browser, scripts and test helpers.
- [x] 2026-10-08: review/update diagram and all three source-linked guides;
  data-flow edges, settings and timing scopes are unchanged.
- [x] 2026-10-08: audit all 170 named Python functions across 28 files; all
  parameters (except implicit self) and returns annotated, Args/Returns present.
  All ten lambdas became named documented callbacks. Each executable logical
  Python statement has a preceding explanation; bracket-only lines are excluded.
- [x] 2026-10-08: 48 existing tests run: 46 pass, 2 skip (OpenCV absent and
  restricted loopback binding). No assertions removed and no dependency installed.
- [x] 2026-10-08: normalized executable AST matches for all 26 original Python
  files after stripping types/docstrings and expanding callbacks back to their
  original expressions. Shell executable lines match the original helpers.
- [x] 2026-10-08: browser differential check matches 16 render states and two
  polling cases (success/disconnection); CSS values unchanged. This is a
  synthetic DOM/canvas check, not a physical browser or Pi performance test.
- [x] 2026-10-08: Python compilation and shell syntax checks pass; project layout
  check passes. All 61 learning/diagram relative links resolve. All 1,712 logical
  Python statements in source/tests/check script have preceding explanations.
- [x] 2026-10-08: all nine CLI module help checks and four standalone-script help
  checks pass without loading hardware; optional driver/OpenCV imports stay lazy.
- [x] 2026-10-08: round-trip patch verification matches all 33 packaged files;
  apply the patch to Desktop with scoped permission approval, preserving prior
  documentation changes. Desktop checks: 48 tests run, 47 pass, one skips because
  OpenCV is unavailable; contract audit, shell syntax and project layout pass.
- [ ] User reviews changes and commits/pushes to make them available on the Pi.
- [ ] Run the existing Pi smoke checks and record the observations.

## Plan of work

1. Documentation foundation: `docs/PIPELINE.md` with Mermaid and a textual
   fallback, plus `docs/learning/{README,IMAGE_MOTION,OBJECT_DETECTION,IMU}.md`.
   Use named functions and repository-relative source links so the docs work on
   GitHub and don't depend on one person's Mac path. Distinguish current and
   future functionality. Add an explicit diagram-update check to every ExecPlan.
2. Behavior-preserving readability: expand packed statements and use descriptive
   local names. Add a preceding or inline comment for each executable logical
   statement; explain multi-line expressions as one operation rather than adding
   noise to closing brackets, blank lines or docstrings. Explain why and units,
   not merely repeat the syntax. Comment imports and module constants by purpose.
3. Python contracts: annotate every explicit function parameter and return value,
   with `self` understood as the owning class. Give every function/method/test
   helper a triple-quoted docstring covering purpose, Args, Returns and important
   errors/side effects. Include array shapes, units, timestamp clock and ownership.
   Use small aliases/Protocols/TypedDicts where they clarify existing structures;
   no elaborate typing framework and no new runtime dependencies. Keep optional
   hardware/OpenCV imports optional. Use postponed annotations as needed.
4. Other languages: use JSDoc `@param`/`@returns` for browser functions and object
   payloads; use shell comments describing arguments, environment and exit codes.
   Triple-quoted Python docstrings are not valid JavaScript or shell syntax.
   Expand one-line browser logic into teachable statements; preserve behavior.
5. Read-through/audit: walk the three guides against actual code, regenerate
   accurate source references and test all changed code, not only the happy path.

## Concrete steps

Work in a writable snapshot containing no raw recordings or model weights.
Run `PYTHONPATH=src python3 -m unittest discover -s tests/unit -v` before and after
each batch. Run `bash scripts/check_project.sh`, shell syntax checks and Python
compilation. Validate browser JavaScript syntax if an existing JS runtime is
available; do not install one silently. Check every new relative Markdown link.
Use an AST audit for missing function docstrings/parameter/return annotations;
review comments manually for meaningful coverage. Compare algorithms/constants
and serialized fields with the baseline, not just test pass counts.

## Validation and acceptance

- The current Mermaid pipeline and plain-language fallback are tracked docs.
- Each guide covers entry point -> input -> transformation -> shared state -> UI,
  plus timing, failure handling, tests and exercises in the actual implementation.
- Every first-party Python function has the agreed annotations/docstring coverage;
  browser functions have JSDoc and shell inputs have comments.
- Executable steps have instructional comments; no algorithm/setting change is
  smuggled into the refactor. Any discovered bug is reported separately.
- Existing tests retain their assertions and all runnable checks pass. Report
  optional-dependency/socket skips honestly; passing unit tests is not Pi proof.
- Pi follow-up: same existing camera, scene, 720p MJPEG/30 mode and live flags;
  compare a still interval and slow turn/return with previous observations.
  Do not claim timings are identical without measuring them on the Pi.

## Surprises and discoveries

- The Desktop repo has no applied object-ID tracker; document detection boxes,
  not a tracking system. Prior scratch patches are not this repo's source of truth.
- Unit tests can create files beneath `recordings/`; a read-only checkout cannot
  execute the whole suite even though these tests require no physical camera.

## Decision log

- 2026-10-08: separate documentation groundwork from code edits so the user can
  read the plan first, following the repository's explicit planning rule.
- 2026-10-08: interpret line-by-line comments as every executable logical step,
  including tests/helpers, not syntactic punctuation. Retain clear existing
  comments instead of duplicating them. No model/driver/third-party refactor.
- 2026-10-08: study order: image motion, object detection, IMU, as requested in
  the annotation; each guide remains independently navigable.
- 2026-10-08: use one small `_contracts.py` vocabulary, imported only for type
  checking, so direct hardware scripts do not gain runtime path/dependency
  requirements. Use Any explicitly at optional native-runtime/report boundaries;
  document concrete shapes and units rather than inventing a large typing layer.
- 2026-10-08: retain existing algorithms/defaults/file schemas and module
  docstrings (used by CLI help). Named callbacks preserve the original closure
  expressions and invocation sites. Do not bundle feature changes or bug fixes.
- 2026-10-08: add a dependency-free structural contract check script so future
  code additions can preserve this documentation convention.

## Outcomes and retrospective

Implementation and local verification are complete in the Desktop repository.
Runtime source, tests, browser and scripts are expanded/commented and the
guides explain how to read the new contracts. The preserved diagram remains
the current pipeline: no tracking, fusion, model or scheduling change was added.

The delivered code patch has been applied to Desktop. Do not apply it again.
Existing uncommitted roadmap/AP-agenda and documentation-foundation changes were
preserved. No commit or push was performed; review the combined working-tree
diff and commit/push only the intended files.

Keep this plan active until the user has completed a Pi
smoke check under the existing protocol. Confirm camera, arrow, gyro statuses,
boxes and orderly Ctrl+C; record any performance observations with the same
measurement scope. Do not claim equal Pi timing merely because unit tests pass.
