# Provisional IMU-to-camera axis mapping

This is an **offline, neutral-head mounting estimate** for the current camera-
mounted SH3001. It gives camera-relevant directions to gyro vectors; it does
not yet feed the live preview or establish world orientation. The application
goal is to make relative viewing direction interpretable. The AP question after
validation is how much compute the small transform adds at the achieved IMU rate.

## Coordinate convention

At the neutral camera pose, camera `+X` points right, `+Y` points down and
`+Z` points forward through the lens. This is a right-handed frame. A positive
rotation about camera X points the lens up; a positive rotation about camera Y
points it right. These are **rotation axes**, not an object's image coordinates.

The user observed the first negative-command tilt leg pointing the lens **up**.
The earlier negative-command pan sweep was observed pointing the lens **right**.
The tool requires both observations explicitly rather than inferring physical
direction from servo command signs. The camera/IMU attachment must remain rigid.

## Data and fit

The pan source is `orientation-pan-10ms-01-data` and the tilt source is the
transferred `orientation-tilt-10ms-01-data`, both on the Mac outside Git. Each
run uses its own two-second still gyro offset and host-stamped actual servo
commands. The transferred tilt files contain **653 IMU samples and 215 decoded
frames**. An earlier pasted terminal output reported 666 and 217; those are
different runs and their values must not be mixed.

For each run, `spatial.camera_axes.movement_legs` integrates corrected XYZ
angular rates over the negative, positive and return command legs. The windows
start 25 ms before each leg's first command and end 120 ms after its last;
these are approximate response margins, not measured shaft motion. The first
two legs determine a direction; the final leg checks whether it points back.

| Leg | Pan IMU XYZ integral (degrees) | Tilt IMU XYZ integral (degrees) |
|---|---:|---:|
| First negative command | (+3.41, +17.98, +0.14) | (−0.02, +0.04, +1.06) |
| Through positive command | (−7.16, −38.06, −0.75) | (+0.15, −0.08, −1.57) |
| Return to zero | (+3.58, +18.40, −0.07) | (−0.07, +0.10, +0.54) |

The raw fitted pan/tilt directions are **87.37° apart**. The held-out final
leg differs from its expected fitted direction by **1.02° for pan** and
**8.79° for tilt**. The small tilt sweep has less angular signal; its return
check supports the sign but is not a precision calibration.

The candidate camera axes, expressed as unit vectors in IMU XYZ, are:

| Camera axis | IMU X | IMU Y | IMU Z |
|---|---:|---:|---:|
| `+X` right; positive pitch points lens up | −0.0551 | +0.0434 | +0.9975 |
| `+Y` down; positive yaw points lens right | +0.1882 | +0.9816 | −0.0323 |
| `+Z` forward, completed by right-handed cross product | −0.9806 | +0.1860 | −0.0622 |

The first two measured directions are orthogonalized before constructing Z.
For a bias-corrected IMU rate `(gx, gy, gz)`, camera-X rate is its dot product
with the first row, camera-Y rate with the second, and camera-Z rate with the
third. The same rotation of coordinates can be applied to a relative rotation
vector. These components are still degrees/second or degrees, respectively;
they are not Euler angles, position or compass heading.

Reproduce the **read-only** fit on the Mac:

```bash
cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 -m spatial.camera_axes \
  /Users/ryanchoi/Desktop/orientation-pan-10ms-01-data \
  /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data \
  --pan-first right --tilt-first up
```

The fit rejects weak or directionally inconsistent legs, nonorthogonal pan/
tilt fits, incomplete runs and invalid timing. Its `camera_components` helper
is pure math and can be tested without a Pi. The third leg is held out during
the fit, but it is still part of the **same recording**. The optional
`--validate-folder` checks a separate recording with sequential pan and tilt
legs against the original fixed basis. The report includes each leg's magnitude,
direction error and status. An independent leg needs at least 0.4° integrated
motion and no more than 20° direction error to pass. A weak leg is reported as
`inconclusive_weak` even if its direction seems plausible; its angle is
noise-sensitive. A strong wrong-direction leg is `direction_mismatch`.
The CLI prints the complete JSON report and exits with status 2 when the
independent check is not `pass`, so scripts cannot mistake a reported weak leg
for a successful validation.

The independent `orientation-axis-validation-01-data` capture contained 845
IMU samples and 293 decoded frames. With the original basis unchanged, all
three pan legs passed (1.82–3.27° magnitude; 2.18–2.76° error). The first two
tilt legs passed (0.95°/5.00° and 2.11°/1.20°). The final tilt return was only
**0.255°**, below the 0.4° minimum. Its computed direction error was 20.08°,
but that borderline angle is not reliable with such weak movement. The final
result is **inconclusive**, not validated and not evidence that the fitted axes
are wrong. The last tilt command occurred around 7.75 s after the recording
origin; its small gyro response was near that command and the sensor was nearly
still after roughly 7.9 s. Merely extending the analysis window would not
recover a clear turn. The capture used a ±2° *servo command* sweep, not a
measurement of physical head travel. The user reviewed the saved video and
confirmed that the lens turned **right first, then left**, followed by **up,
then down**. Thus the independent recording's physical pan/tilt signs agree
with the fit inputs; the weak final tilt leg remains inconclusive.

The initial combined run alone was insufficient for live use. The large
difference between the two runs' raw stationary gyro offsets also reinforces
why each run needs its own still bias. Accelerometer calibration remains
untrusted; the transform does not use it. Neither servo commands nor host
timestamps supply a camera/IMU exposure alignment or a measured motor angle.

## Independent tilt-only check and bias-window reanalysis

The dedicated `--axis-validate-tilt` recorder mode commanded one supervised
`0° → −6° → +6° → 0°` tilt sweep at 5 commanded degrees/s, with one-degree
steps. It does not command pan. The ±6° test amplitude is smaller than the
user-confirmed ±25° safe tilt range and matches the recorder's existing tilt
software limit. Its initial two-second-plus still period supports an independent
per-run gyro bias. The recorded command times, not ideal schedule times, define
the three integration windows. Servo commands are not measured shaft angles.

After reviewing physical clearance and confirming the camera device on the Pi,
run this from the repo root after the updated code is pulled. Close other
camera users first; `--execute` is the boundary that actually moves the motor.

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m recording.servo_motion_quality \
  --axes tilt --axis-validate-tilt --imu-interval 0.01

sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
  --axes tilt --axis-validate-tilt --execute \
  --confirm-centered --confirm-cable-slack --confirm-commissioned \
  --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
  --imu-policy fixed --imu-interval 0.01 \
  --output recordings/orientation-tilt-validation-02 \
  --scene "fixed base; neutral pan; supervised tilt-axis validation" \
  --power "unknown" --cooling "passive metal heatsink"
```

The first command should point the lens up, the middle leg should reverse it,
and the last leg should return it toward center. Stop with Ctrl+C if the head
binds or a cable pulls; interruption does not automatically drive the servo
through a possible obstruction. Do not reuse an existing output folder.
Transfer `metadata.json`, `imu.csv` and `servo_commands.json` to a new Mac
folder. The analysis below re-fits only the **original two source recordings**
and checks the new tilt recording against that unchanged basis. It does not
pretend the new tilt-only recording retested pan:

```bash
mkdir -p /Users/ryanchoi/Desktop/orientation-tilt-validation-02-data
scp pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-tilt-validation-02/{metadata.json,imu.csv,servo_commands.json} \
  /Users/ryanchoi/Desktop/orientation-tilt-validation-02-data/

cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 -m spatial.camera_axes \
  /Users/ryanchoi/Desktop/orientation-pan-10ms-01-data \
  /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data \
  --pan-first right --tilt-first up \
  --validate-tilt-folder /Users/ryanchoi/Desktop/orientation-tilt-validation-02-data
```

This default command **failed before checking the tilt legs**: the first
two-second bias window contained a large early gyro transient. The completed
recording has 907 IMU samples and 24 issued tilt commands. In the first 0.25 s
after the cue, gyro Y reached about 57°/s; the cause is unknown. The first
motor command was about 2.7 s after the cue. The user approved an explicit,
retrospective reanalysis using the stable 1.0–2.5 s pre-command window:

```bash
PYTHONPATH=src python3 -m spatial.camera_axes \
  /Users/ryanchoi/Desktop/orientation-pan-10ms-01-data \
  /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data \
  --pan-first right --tilt-first up \
  --validate-tilt-folder /Users/ryanchoi/Desktop/orientation-tilt-validation-02-data \
  --validation-bias-start 1.0 --validation-bias-seconds 1.5
```

The software records that window and rejects one that overlaps the first
command (with a 0.1 s margin). It still requires at least five samples, no
IMU gap over 0.2 s, and stationary standard deviation at most 2°/s on every
gyro axis. It does not relax either movement-leg criterion. For this saved
run, the revised window contains 124 samples; gyro XYZ standard deviations
are (0.213, 0.182, 0.182)°/s. With the original fitted basis unchanged, the
tilt legs have magnitudes **2.12°, 7.26°, 1.95°** and signed-axis deviations
**5.00°, 2.36°, 6.05°**. All three pass the existing numerical criteria. The
report labels `analysis_protocol` as `explicit_bias_window`; for this run, the
window was selected retrospectively, not in the original plan. It checks only
tilt, not pan, and
the user's observation of this new run's physical first direction remained
unknown because the lens was covered. Its numerical pass is preserved as a
separate, retrospectively selected-window result, not rewritten as a fully
observed validation.

`independent_validation.axes_checked` must be `["tilt"]`. All three new tilt
legs need at least 0.4° integrated IMU motion and no more than 20° deviation
from their signed expected axis; otherwise the result stays inconclusive or
fails. The earlier independent pan result remains separate evidence. Keep the
basis offline until the new data and physical movement are reviewed.

### Uncovered-lens repeat and AP cost check

The user repeated the same tilt-only schedule with the lens uncovered as
`orientation-tilt-validation-03` and confirmed the **first lens movement was
up**. The capture completed with 311 decoded-frame records and 910 IMU samples;
24 one-degree tilt commands were issued. The source pan/tilt fit remained
unchanged. With the **preselected** 1.0–2.5 s still window, 125 bias samples
had gyro XYZ standard deviations (0.190, 0.188, 0.113)°/s. The three new tilt
legs measured 4.57°, 7.32° and 1.74° of integrated IMU rotation, with
signed camera-axis deviations 2.76°, 1.09° and 3.11°. All exceed the 0.4°
signal minimum and fall below the 20° direction limit. The earlier independent
combined run had already passed all three **pan** legs. Together these are
separate, physically signed pan and tilt direction checks of the neutral-head
mapping. They do not calibrate shaft angle, timing alignment, world pose or
depth. The automatic horizontal-image/gyro-Y correlation is a pan-oriented
exploratory diagnostic, not this tilt validation's acceptance metric.

Before adding this transform to the live worker, measure its **compute cost**
on the Pi with the read-only, no-camera/no-servo benchmark. It refits the
existing source recordings before timing only repeated calls to
`spatial.camera_axes.camera_components`; the fit and CSV reads are excluded
from the timed loop. Close the live preview and use the same Pi software and
cooling when comparing runs:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.camera_axis_cost \
  recordings/orientation-pan-10ms-01 \
  recordings/orientation-tilt-10ms-01 \
  --pan-first right --tilt-first up \
  --warmup-seconds 1 --measure-seconds 5
```

Run it three times and retain each JSON report with the commit, host, Python
version, fitted basis, durations and CPU/elapsed-time metrics. The reported
`process_cpu_us_per_call_total` includes benchmark-loop and timer overhead, so it is a
conservative allocation estimate rather than isolated arithmetic time.
The 20, 30 and 100 Hz CPU percentages are **projections** from that single-call
cost, not measured sensor rates or live-pipeline CPU savings. This benchmark
uses a fixed finite gyro vector; it does not read I2C, open the camera, move
motors or integrate an orientation. Camera mode, scene and power are not
applicable during this isolated CPU experiment; the Pi is the device under
test. A later integrated benchmark must measure real scheduling/contention
before choosing the live conversion rate.
