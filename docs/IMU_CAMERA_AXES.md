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

The code rejects weak or directionally inconsistent legs, nonorthogonal pan/
tilt fits, incomplete runs and invalid timing. Its `camera_components` helper
is pure math and can be tested without a Pi. The third leg is held out during
the fit, but it is still part of the **same recording**. The optional
`--validate-folder` checks a separate recording with sequential pan and tilt
legs against the original fixed basis. It rejects weak motion or a leg more
than 20° from the expected camera axis. A separate controlled run is needed
before applying this mapping in the live worker. The large
difference between the two runs' raw stationary gyro offsets also reinforces
why each run needs its own still bias. Accelerometer calibration remains
untrusted; the transform does not use it. Neither servo commands nor host
timestamps supply a camera/IMU exposure alignment or a measured motor angle.
