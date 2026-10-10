# Reading the annotated code

This refactor expands compressed statements and adds teaching material without
changing algorithms, CLI defaults, file schemas or hardware settings. The
three [pipeline guides](README.md) remain the reading order: image motion,
object detection, then IMU.

## Function signatures and docstrings

For example, `read_frame(stream: BinaryIO, size: int) -> bytes | None` says the
caller supplies a readable binary stream and integer byte count; the function
returns immutable bytes or the explicit absence value `None`. It does not
mean a short byte string is acceptable as a complete frame. The docstring
explains end-of-stream behavior and the code raises an error on a partial frame.

Every named Python function, nested helper and test double has parameter and
return annotations and an Args/Returns docstring. `self` is implicitly the
instance of its enclosing class. Physical units and array shapes live in the
docstring because a plain float/array type cannot express those distinctions.
Comments explain **groups of statements that perform one task**, not each line.
Existing module docstrings remain intact because the command-line help uses them.

## Task-level comments (updated 2026-10-10)

Place one concise explanation above a cohesive operation: parsing command-line
options, validating input, selecting a latest frame, computing motion, publishing
shared state, rendering a metric group, or cleaning up resources. Use blank lines
to make those boundaries visible. Group by purpose, not a fixed number of lines.

Explain why the group exists and any non-obvious constraints: units, array shapes,
clock origin, lock ownership, freshness policy and deliberate frame skipping.
Keep a narrowly placed comment when an individual operation genuinely needs one.
Avoid comments that merely say to assign a value, call a function or return.
Short self-explanatory helpers may need only their existing function docstring.
Tests should explain the scenario and expected behavior in groups, without
narrating each assertion. Preserve docstrings and type annotations as contracts.

For example, all `add_argument(...)` calls and `parse_args()` belong beneath one
comment about defining/parsing the command-line configuration. Validation and
hardware startup are separate tasks and deserve separate explanations.

Anonymous lambdas have become ten named callbacks, such as `motion_frame_ready`,
`build_detector` and `read_hash_block`. A callback is a function passed to other
code to call later. It is not necessarily a thread. These callbacks still
capture the same surrounding values and evaluate the same expressions when
called. The condition predicates can return a nonempty error string as a truthy
value, hence their `bool | str` return annotation rather than pretending every
result is a literal boolean.

## Small shared vocabulary

[src/_contracts.py](../../src/_contracts.py) defines:

| Name | Meaning |
|---|---|
| `Axes` | Three XYZ floats; caller specifies g, degrees/s or degrees |
| `TimedGyro` | Monotonic host seconds paired with XYZ degrees/s |
| `SensorSample` | Acceleration XYZ g paired with gyro XYZ degrees/s |
| `Frame` | Sequence integer, host receipt seconds, immutable grayscale bytes |
| `MotionShift` | dx/dy pixels, agreeing-patch count, peak-quality value |
| `NumericRow` | CSV column name to numeric value |
| `Record` | Flexible heterogeneous report/snapshot dictionary |
| `Sensor` | Read-only protocol exposing `read_raw()` and its returned units |

These are descriptions, not runtime wrappers, validation or conversions.
`Record` uses `Any` for heterogeneous nested report fields; the producing
function, guide and tests explain the exact schema. Optional native OpenCV
module/network boundaries also deliberately use `Any` rather than a large,
fragile imitation of the OpenCV API. Numeric arrays are annotated as NumPy
arrays with dtype/shape specified in each boundary's docstring.

## Why TYPE_CHECKING and postponed annotations appear

`from __future__ import annotations` postpones evaluation of type expressions.
`if TYPE_CHECKING:` imports vocabulary for editors without loading it during
execution. In particular, direct commands such as `python3 src/imu/rotation_test.py`
must not suddenly require a modified import path or NumPy/OpenCV just to read
their type hints. Existing optional runtime imports stay where they were.

Annotations do not validate a caller's input at runtime. The existing explicit
checks still do that. Likewise, this change has not introduced or run a full
static type checker. Runtime `typing.get_type_hints()` would need the guarded
names supplied in its namespace; the application does not use that reflection.

## Browser and shell documentation

[preview.html](../../src/app/preview.html) uses JSDoc for `put`, `fmt`, `render`
and `poll`, plus typedefs describing snapshot and detection fields. Its image
copy, overlay geometry, status branches, timing and failure paths are expanded
and commented by task. CSS comments cover layout/style groups rather than every
declaration. HTML comments explain the canvas and metric-group wiring.

Shell scripts have no user-defined functions. Their top comments specify
arguments, environment assumptions, outputs and exit behavior; executable
groups explain why commands are read-only. No command was added to install
software, change permissions or configure hardware.

## Repeating local checks

From the repo root, with the existing environment:

```bash
python3 scripts/check_learning_contracts.py
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
bash -n scripts/check_project.sh scripts/hardware_inventory.sh
bash scripts/check_project.sh
```

The contract audit parses files; it does not import sensor modules. It reports
missing parameter/return annotations, missing docstring sections and anonymous
callbacks. It cannot judge prose correctness, units or algorithm behavior.
Review source and run behavioral tests too. No formatter is needed to execute
the application; the refactor used an already-installed Black formatter.

During development, a normalized-AST comparison checked all 26 original Python
files after erasing type/docstring additions and inlining the ten named
callbacks. Their executable operations matched the original. Shell executable
lines also matched exactly. A synthetic browser comparison matched DOM text,
canvas calls and polling behavior in 16 rendering cases plus two polling cases;
CSS declarations matched ignoring comments/formatting/optional trailing semicolons.
Those comparisons are evidence for the original typed-code refactor, not a promise of identical
measured Pi performance or a substitute for a real browser/hardware smoke test.

The later grouped-comment pass preserves the entire Python AST, including
docstrings and types. Comments and whitespace are not executable instructions;
the function-contract audit remains useful but cannot assess comment quality.
