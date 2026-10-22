# Camera-based spatial awareness: research and EdgeXR recommendation

Research date: 2026-10-23. Scope: primary research, author implementations and
official geometry/calibration documentation relevant to a Pi 4, one grayscale
USB camera and a camera-mounted IMU. This is a focused engineering review, not
an exhaustive literature survey or a reproduced benchmark. No software installed.

## Recommendation

Build a **relative visual compass and bounded directional scene memory** first.
Keep the base fixed, estimate camera rotation, save representative scene
keyframes, and verify revisits geometrically. This recommendation is our
engineering inference from the sources below and EdgeXR's current measurements,
not a published claim that this exact rig will achieve a given accuracy or FPS.

Separate four capabilities: angular orientation; remembering viewing directions;
translation/3D reconstruction; and semantic object naming. The first two are
our next objective. Full SLAM and object re-identification are not prerequisites.

## Useful papers and what they change in our plan

### 1. Pan/tilt alignment: closest mechanical match

Knight and Reid, *Automated Alignment of Robotic Pan-Tilt Camera Units Using
Vision*, IJCV 2006. The authors derive platform alignment from image
transformations during controlled single-axis rotations, accounting for the
relationship between optical and mechanical axes. This is directly relevant to
our camera mounted on a head: commanded zero is not a calibrated optical frame.
We borrow the calibration question, not claim to reproduce their full method.
[Author publication page](https://www.robots.ox.ac.uk/~lav/Papers/knight_reid_ijcv2006/knight_reid_ijcv2006.html).

### 2. Image alignment and panoramas: surroundings without a depth map

Szeliski, *Image Alignment and Stitching: A Tutorial*, MSR-TR-2004-92, 2004,
provides the alignment/panorama framework. A direction-indexed set of overlapping
views can remember surroundings without reconstructing every object's depth.
Our first deliverable is a keyframe memory, not a seamless panoramic renderer.
[Author publication](https://www.microsoft.com/en-us/research/publication/image-alignment-and-stitching-a-tutorial/).

The official OpenCV geometry tutorial gives the pure-rotation relation
`p2 ~ K R21 K^-1 p1`, for undistorted homogeneous image points. `K` is calibrated
camera intrinsics; `R21` maps rays from camera 1 to camera 2. Scene depth cancels
for pure rotation about the optical center. A generic fitted homography is not
automatically a valid camera rotation: translation over a plane can also explain
it. Validate the rotation model, spatial coverage and residuals.
[OpenCV homography tutorial](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html).

**Implication for our rig:** the camera optical center is offset from the servo
axis, so pan/tilt produces some translation. Nearby objects can exhibit parallax.
Start with a textured background at some distance, then deliberately test mixed
depths. Reject model failure rather than silently treating it as rotation.

### 3. ORB-SLAM: features, keyframes, revisits and maps

Mur-Artal, Montiel and Tardós, *ORB-SLAM: a Versatile and Accurate Monocular
SLAM System*, 2015, describes feature-based tracking, mapping, relocalization
and loop closure. It suggests useful architecture: retain selected keyframes,
match scene landmarks, and verify a revisit rather than simply compare object
labels. We can borrow bounded feature matching without porting the entire
backend. General monocular geometry needs translational parallax to triangulate
depth; pure rotation does not recover it, and monocular metric scale needs
additional information.
[Paper](https://arxiv.org/abs/1502.00956).

### 4. ORB-SLAM3: later visual-inertial/3D option

Campos et al., *ORB-SLAM3*, IEEE T-RO 2021, supports visual and visual-inertial
SLAM, including monocular input and map reuse. Its initialization estimates
inertial quantities, not merely camera rotation. That makes it a strong later
candidate, but not a drop-in replacement for our current gyro display.
[Paper](https://arxiv.org/abs/2007.11898).

The official repository recommends a powerful computer for stable real-time
operation and lists C++ dependencies; it is GPLv3. This is not evidence of
real-time performance on our Pi 4 with concurrent detection and recording.
[Author code and prerequisites](https://github.com/UZ-SLAMLab/ORB_SLAM3).

### 5. SVO: efficient visual odometry, not automatic surroundings memory

Forster, Pizzoli and Scaramuzza, *SVO: Fast Semi-Direct Monocular Visual
Odometry*, ICRA 2014, combines direct image alignment and feature-based geometry.
It is relevant if the base later translates and efficiency becomes critical.
Odometry is motion estimation; a useful persistent revisit/map system needs
additional design. The original author repository documents old ROS/Ubuntu
targets, so adoption would require a compatibility and maintenance audit.
[Author repository with paper](https://github.com/uzh-rpg/rpg_svo).

### 6. VINS-Mono and OpenVINS: make the IMU useful, with prerequisites

Qin, Li and Shen, *VINS-Mono*, T-RO 2018, couples camera features with IMU
measurements, initialization and relocalization. Its demonstrated mobile
implementations show that low-cost camera/IMU sensing is a meaningful path,
not that an arbitrary slow or poorly synchronized IMU is sufficient.
[Paper](https://arxiv.org/abs/1708.03852).

*OpenVINS: A Research Platform for Visual-Inertial Estimation* and its author
documentation provide a filter-based alternative with explicit uncertainty and
calibration tooling. Consider it alongside ORB-SLAM3/VINS-Mono if we move to
6-DoF estimation; do not choose a winner without Pi measurements.
[Author documentation and citation](https://docs.openvins.com/).

Kalibr's camera–IMU guide requires appropriate sensor calibration/noise models
and supports temporal calibration. This reinforces that common host clocks do
not equal exposure synchronization. Full inertial calibration is later work;
we can first measure short-term gyro-only rotation without trusting the known
problematic accelerometer calibration.
[Official calibration guide](https://github.com/ethz-asl/kalibr/wiki/camera-imu-calibration).

### 7. Fiducials: optional measurement reference, not the final environment

Olson, *AprilTag*, ICRA 2011, and Wang and Olson, *AprilTag 2*, IROS 2016,
describe identifiable visual markers and efficient detection. A printed target
of known geometry, calibrated camera and pose solver can provide a reference
for orientation tests. It still has uncertainty and pose ambiguities; it is not
perfect ground truth. Keep target-assisted evaluation separate from markerless
scene-memory evaluation. Ask before adding a target or dependency.
[Original paper](https://april.eecs.umich.edu/papers/details.php?name=olson2011tags),
[AprilTag 2](https://april.eecs.umich.edu/papers/details.php?name=wang2016iros),
[Author system description](https://april.eecs.umich.edu/software/apriltag.html).

## What evidence exists specifically for Raspberry Pi?

A developer's [Pi 4 ORB-SLAM3 implementation report](https://github.com/Lochan25526/ros2-orbslam3-vio)
reports a working monocular configuration but non-convergent inertial
initialization. This is first-party implementation evidence, not peer-reviewed
validation or a benchmark we reproduced. It uses different camera/IMU hardware,
ROS and patches. Do not transfer its FPS or CPU numbers to EdgeXR.

This search did not establish a peer-reviewed benchmark matching **Pi 4 + our
OV9281 USB bridge + SH3001 + concurrent EdgeXR workload**. No hardware upgrade
is justified by that absence alone. Prototype a bounded visual rotation front
end on saved frames, then measure it on the Pi before selecting a full SLAM stack.

## Selection summary (engineering judgment)

| Approach | Useful output | Current decision |
| --- | --- | --- |
| Existing FFT patch shift | Local image displacement | Keep diagnostic baseline; not angular pose |
| Calibrated feature/ray rotation + keyframes | Relative orientation and remembered directions | Next milestone |
| Gyro-assisted relative orientation | Short-term propagation between visual updates | Add after axis/timing checks |
| ORB-SLAM3 / VINS / OpenVINS | Broader pose/map capability depending on system | Later gated experiment |
| SVO | Efficient odometry | Later translation candidate |
| Fiducial reference | Measurable reference orientation | Optional validation aid |
| More person re-ID tuning | Identity continuity | Paused; does not solve pose |

## Conditions that can invalidate our first approach

- Translating the base, close-range parallax or a loose camera–IMU mount.
- Moving people dominating features, repeated shelf patterns, blank walls,
  exposure change, blur, or non-overlapping views.
- Integrating gyro across missing samples, bias drift, unknown axis signs or
  treating independently integrated XYZ values as general Euler angles.
- Incorrect intrinsics after resizing/cropping; changing focus invalidating
  calibration; using command angles as measurement truth.
- Mistaking scene resemblance for geometric agreement or an unobserved region
  for empty/free space. This map will not be safe for collision avoidance.

Use explicit `unknown`, loss of confidence and bounded storage. Neither a
seamless panorama nor an elaborate UI is an acceptance criterion. The next
[implementation plan](exec-plans/active/orientation-aware-surroundings.md)
turns these research findings into measured gates.
