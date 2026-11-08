# Add bounded 3D reconstruction before FPGA implementation

## User direction

On 2026-11-08 the user explicitly extended the earlier finish line: finish the
spatial application, add 3D reconstruction, then advance to FPGA implementation
for systems/AP learning. AP remains the primary learning goal. This supersedes
the earlier exclusion of reconstruction from the pre-FPGA roadmap, but does not
mean reconstruction already exists or authorize new packages/hardware purchases.

## Proposed measurable 3D endpoint (scope to confirm)

**Calibrated offline sparse reconstruction of one static tabletop or room
corner**, yielding a 3D point cloud and estimated camera poses, saved in a
documented format with error/coverage diagnostics. This is genuine but limited
3D reconstruction. It is not a dense photorealistic room mesh, continuous live
SLAM, collision-safe navigation or a promise of metric distances.

Dense mesh/live reconstruction are additional scopes if the user means those
by “complete 3D”; do not silently call sparse reconstruction equivalent to them.

## Sequence

1. Resolve foreground enrollment feedback; validate a stored left view during
   crossing. Add bounded semantic memory and quality-gated motion/IMU context.
2. Freeze the integrated application and preserve a repeatable reference run.
3. Calibrate camera intrinsics/distortion at the exact fixed image mode/focus.
4. Capture a static textured scene with overlapping **translated** viewpoints.
   Move safely with slack cables; existing pan/tilt sweep alone is not enough.
5. Match features, estimate multi-view geometry and triangulate; reject weak
   parallax, negative-depth and high-reprojection-error estimates. Refine poses
   and points with an established method rather than claim the homography is 3D.
6. Export sparse points/poses; measure registered views, support distribution,
   reprojection errors and held-out-image agreement. Label arbitrary scale.
   If metric scale is needed, use a known reference and validate another length.
7. Record runtime/memory on the actual execution device; a Mac reconstruction
   is not a Pi performance result. Then start the FPGA hardware milestone using
   the Pi workload as reference. Simulation/toolchain checks may occur earlier.

## Why the current hardware imposes these conditions

A monocular camera can support multi-view reconstruction without buying a depth
camera, but the camera center must move enough to provide parallax. Pure rotation
does not reveal distance; pivot offset is not a calibrated depth baseline. Gyro
orientation alone does not supply metric scale or camera translation.
[COLMAP's tutorial](https://colmap.github.io/tutorial.html) distinguishes sparse
Structure-from-Motion (points/poses) from dense multi-view stereo.
[OpenCV pose geometry](https://docs.opencv.org/4.6.0/d9/d0c/group__calib3d.html)
describes recovered translation up to scale. No COLMAP installation or new
camera purchase has occurred. We may begin with existing camera plus a printed
calibration target on a rigid flat backing and a ruler; procedure comes first.

## Boundaries and AP learning

Set acceptance before implementation so “finish 3D” does not postpone AP work
indefinitely. Sparse reconstruction exposes feature matching, numerical kernels,
memory traffic and batch scheduling. FPGA work must measure whole-path benefit,
including transfers, not just hardware compute. Budget research is in
[FPGA_PURCHASE_SHORTLIST.md](../FPGA_PURCHASE_SHORTLIST.md).
