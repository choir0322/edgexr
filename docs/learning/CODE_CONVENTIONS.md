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
Comments explain executable logical statements; continuation lines, parentheses
and blank lines do not need redundant comments. Existing module docstrings
remain intact because the command-line help uses them.

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
and commented. CSS declarations have explanations but retain their existing
values. HTML comments explain the canvas and metric-group wiring.

Shell scripts have no user-defined functions. Their top comments specify
arguments, environment assumptions, outputs and exit behavior; executable
steps explain why commands are read-only. No command was added to install
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
Those comparisons are evidence for this change, not a promise of identical
measured Pi performance or a substitute for a real browser/hardware smoke test.
