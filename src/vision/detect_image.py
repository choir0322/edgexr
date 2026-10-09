"""Measure MobileNet-SSD on one saved monochrome image; no camera or downloads."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Any, Iterable, Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np

    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Record


# Parse and validate explicit command-line options.
import argparse

# Fingerprint model/image artifacts without committing their large contents.
import hashlib

# Read or serialize metadata and browser/report payloads.
import json

# Validate finite numbers and perform scalar numerical calculations.
import math

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Record the operating system/runtime context of a measured run.
import platform

# Compute means, spreads and medians from collected measurements.
import statistics

# Run existing FFmpeg/ffprobe/Git tools with explicit argument lists.
import subprocess

# Measure host intervals and provide bounded polling pauses.
import time


# Prepare LABELS for the next step using the values calculated so far.
LABELS = (
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
)


def parse_detections(
    rows: Iterable[Sequence[float]], width: int, height: int, threshold: float
) -> list[Record]:
    """Validate SSD rows, filter scores and map normalized boxes to source pixels.

    Args:
        rows (Iterable[Sequence[float]]): Named numeric CSV rows or seven-column SSD
            rows, as specified by this function.
        width (int): Original image width in pixels, a positive integer.
        height (int): Original image height in pixels, a positive integer.
        threshold (float): Minimum accepted detection score, inclusive, between zero and
            one.

    Returns:
        list[Record]: Detection dictionaries with class_id, label, confidence and
            integer box_xyxy.
    """
    # Reject this invalid input before it can produce misleading output.
    if width <= 0 or height <= 0 or not 0 <= threshold <= 1:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Invalid image dimensions or confidence threshold")
    # Prepare detections for the next step using the values calculated so far.
    detections = []
    # Process each row in the selected collection.
    for row in rows:
        # Reject this invalid input before it can produce misleading output.
        if len(row) != 7 or not all(math.isfinite(float(v)) for v in row):
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Expected finite SSD rows of seven values")
        # Unpack the seven SSD output fields as numbers.
        batch, label, score, left, top, right, bottom = map(float, row)
        # Choose the next branch using batch == -1.
        if batch == -1:  # SSD may use a sentinel when no detections exist.
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Reject this invalid input before it can produce misleading output.
        if batch != 0 or label != int(label) or not 0 <= label < len(LABELS):
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Unexpected batch or class ID; check model files")
        # Reject this invalid input before it can produce misleading output.
        if not 0 <= score <= 1:
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Invalid detection confidence")
        # Choose the next branch using label == 0 or score < threshold.
        if label == 0 or score < threshold:
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Clip the left boundary to the image and round down in source pixels.
        x1 = math.floor(max(0, min(1, left)) * width)
        # Clip the top boundary to the image and round down in source pixels.
        y1 = math.floor(max(0, min(1, top)) * height)
        # Clip the right boundary to the image and round up in source pixels.
        x2 = math.ceil(max(0, min(1, right)) * width)
        # Clip the bottom boundary to the image and round up in source pixels.
        y2 = math.ceil(max(0, min(1, bottom)) * height)
        # Choose the next branch using x2 <= x1 or y2 <= y1.
        if x2 <= x1 or y2 <= y1:
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Retain this item/chunk for the current calculation or bounded history.
        detections.append(
            dict(
                class_id=int(label),
                label=LABELS[int(label)],
                confidence=score,
                box_xyxy=[x1, y1, x2, y2],
            )
        )
    # Return the documented result to the caller without starting another operation.
    return detections


def timing_summary(values: Sequence[float]) -> dict[str, float]:
    """Summarize finite nonnegative compute-duration measurements.

    Args:
        values (Sequence[float]): Nonnegative elapsed durations in milliseconds; at
            least one value.

    Returns:
        dict[str, float]: Median, nearest-rank p95, minimum and maximum in milliseconds.
    """
    # Reject this invalid input before it can produce misleading output.
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Timing samples must be finite and nonnegative")
    # Prepare ordered for the next step using the values calculated so far.
    ordered = sorted(values)
    # Return the documented result to the caller without starting another operation.
    return dict(
        median_ms=statistics.median(ordered),
        p95_ms=ordered[math.ceil(0.95 * len(ordered)) - 1],
        min_ms=ordered[0],
        max_ms=ordered[-1],
    )


def infer_once(cv: Any, net: Any, gray: np.ndarray) -> tuple[np.ndarray, int, int, int]:
    """Prepare grayscale input and run one pretrained MobileNet-SSD inference.

    Args:
        cv (Any): OpenCV module or test double; Any is intentional for this optional
            native API.
        net (Any): OpenCV DNN network or compatible test double exposing setInput and
            forward.
        gray (np.ndarray): Two-dimensional uint8 grayscale image; preprocessing creates
            3x300x300 input.

    Returns:
        tuple[np.ndarray, int, int, int]: N-by-7 rows plus start/prepared/inferred perf-
            counter nanoseconds.
    """
    # Prepare start for the next step using the values calculated so far.
    start = time.perf_counter_ns()
    # Replication supplies three channels; the scene remains monochrome.
    bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
    # Resize to 300x300 and normalize to about [-1, 1] in the model's input layout.
    blob = cv.dnn.blobFromImage(
        bgr,
        scalefactor=0.007843,
        size=(300, 300),
        mean=(127.5, 127.5, 127.5),
        swapRB=False,
        crop=False,
    )
    # Mark completion of preprocessing before the forward pass.
    prepared = time.perf_counter_ns()
    # Assign the normalized tensor to the existing pretrained network.
    net.setInput(blob)
    # Execute the pretrained graph, including its SSD output processing.
    output = net.forward()
    # Mark completion of inference before parsing/filtering detections.
    inferred = time.perf_counter_ns()
    # Reject this invalid input before it can produce misleading output.
    if output.ndim != 4 or output.shape[:2] != (1, 1) or output.shape[-1] != 7:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Expected SSD output [1, 1, N, 7]; check model files")
    # Return the documented result to the caller without starting another operation.
    return output[0, 0], start, prepared, inferred


def sha256(path: Path) -> str:
    """Hash an input or model artifact incrementally for reproducibility.

    Args:
        path (Path): Local filesystem path read by this operation.

    Returns:
        str: Lowercase SHA-256 hex digest; filesystem errors propagate.
    """
    # Accumulate a SHA-256 fingerprint without loading a whole model into memory.
    digest = hashlib.sha256()
    # Keep these resources scoped so they are released even if the operation fails.
    with path.open("rb") as handle:

        def read_hash_block() -> bytes:
            """Read the next one-megabyte hash block; empty bytes signal end of file.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                bytes: The callback result described above.
            """
            # Evaluate the original callback expression only when the caller invokes it.
            return handle.read(1024 * 1024)

        # Process each block in the selected collection.
        for block in iter(read_hash_block, b""):
            # Add the fields produced by this step while preserving the other report fields.
            digest.update(block)
    # Return the documented result to the caller without starting another operation.
    return digest.hexdigest()


def cpu_temperature() -> float | None:
    """Read the conventional Pi thermal-zone temperature when available.

    Args:
        None.

    Returns:
        float | None: Degrees Celsius, or None if the interface is absent or unreadable.
    """
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Return the documented result to the caller without starting another operation.
        return float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError):
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None


def git_info() -> Record:
    """Record repository revision and dirty state without changing Git.

    Args:
        None.

    Returns:
        Record: Revision/dirty fields, or None values when Git information is
            unavailable.
    """
    # Prepare root for the next step using the values calculated so far.
    root = Path(__file__).resolve().parents[2]
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Read the current Git commit for the benchmark provenance record.
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        # Record whether local changes could make the measured code differ from that commit.
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Return the documented result to the caller without starting another operation.
        return dict(revision=revision, dirty=bool(dirty))
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, subprocess.CalledProcessError):
        # Return the documented result to the caller without starting another operation.
        return dict(revision=None, dirty=None)


def run(args: argparse.Namespace, cv: Any) -> None:
    """Benchmark a saved image, exclude warmups and save boxes plus a reproducibility report.

    Args:
        args (argparse.Namespace): Parsed command-line options (or a compatible test
            fixture); see main for fields.
        cv (Any): OpenCV module or test double; Any is intentional for this optional
            native API.

    Returns:
        None: writes a new annotated PNG and report only after validating inputs/output
            path.
    """
    # Prepare output for the next step using the values calculated so far.
    output = args.output.resolve()
    # Reject this invalid input before it can produce misleading output.
    if not output.is_relative_to(Path("recordings").resolve()) or output.exists():
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError(
            "Choose a NEW directory inside recordings/; run from repo root"
        )
    # Process each path in the selected collection.
    for path in (args.image, args.prototxt, args.weights):
        # Reject this invalid input before it can produce misleading output.
        if not path.is_file():
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError(f"Missing file: {path}; see docs/DETECTION_BASELINE.md")
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np

    # Interpret the image as one grayscale intensity per pixel with explicit dimensions.
    gray = cv.imread(str(args.image), cv.IMREAD_GRAYSCALE)
    # Reject this invalid input before it can produce misleading output.
    if gray is None or gray.size == 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Could not decode the input image")
    # Prepare height, width for the next step using the values calculated so far.
    height, width = gray.shape
    # Request OpenCV parallelism; this neither reserves cores nor sets detector update
    # frequency.
    cv.setNumThreads(args.threads)
    # Keep this baseline on the CPU rather than using an implicit OpenCL path.
    cv.ocl.setUseOpenCL(False)
    # Prepare start for the next step using the values calculated so far.
    start = time.perf_counter_ns()
    # Load the model graph and parameters into the existing OpenCV runtime.
    net = cv.dnn.readNetFromCaffe(str(args.prototxt), str(args.weights))
    # Execute the graph through OpenCV rather than assuming another inference backend.
    net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
    # Select CPU execution explicitly; no GPU/NPU offload is configured.
    net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)
    # Keep one-time model loading separate from measured inference durations.
    load_ms = (time.perf_counter_ns() - start) / 1e6
    # Read starting temperature separately from the inference timing window.
    before = cpu_temperature()
    # Store measured runs; warmup results are excluded later.
    timings = []
    # Process each index in the selected collection.
    for index in range(args.warmup + args.runs):
        # Prepare rows, started, prepared, inferred for the next step using the values
        # calculated so far.
        rows, started, prepared, inferred = infer_once(cv, net, gray)
        # Prepare detections for the next step using the values calculated so far.
        detections = parse_detections(rows, width, height, args.threshold)
        # Stamp completion separately from the source frame's receipt time.
        finished = time.perf_counter_ns()
        # Choose the next branch using index >= args.warmup.
        if index >= args.warmup:
            # Retain this item/chunk for the current calculation or bounded history.
            timings.append(
                dict(
                    preprocess_ms=(prepared - started) / 1e6,
                    inference_ms=(inferred - prepared) / 1e6,
                    postprocess_ms=(finished - inferred) / 1e6,
                    total_ms=(finished - started) / 1e6,
                )
            )
    # Read ending temperature; this is not a continuous thermal measurement.
    after = cpu_temperature()
    # Record benchmark inputs, runtime versions, scope and measured detections.
    report = dict(
        status="complete",
        host=platform.platform(),
        python=platform.python_version(),
        opencv=cv.__version__,
        numpy=np.__version__,
        git=git_info(),
        notes=args.notes,
        image=dict(
            path=str(args.image), sha256=sha256(args.image), size=[width, height]
        ),
        model=dict(
            name="MobileNet-SSD VOC",
            prototxt_sha256=sha256(args.prototxt),
            weights_sha256=sha256(args.weights),
            input_size=[300, 300],
        ),
        preprocessing="grayscale replicated to BGR; direct resize; (pixel-127.5)*0.007843",
        backend="OpenCV CPU; OpenCL disabled",
        requested_threads=args.threads,
        opencv_threads=cv.getNumThreads(),
        threshold=args.threshold,
        warmup_runs=args.warmup,
        measured_runs=args.runs,
        model_load_ms=load_ms,
        temperature_c_before=before,
        temperature_c_after=after,
        timing_scope="same-image compute; excludes image/model loading, drawing, disk, camera and display",
        p95_method="nearest rank",
        timings={
            key: timing_summary([row[key] for row in timings]) for key in timings[0]
        },
        samples=timings,
        detections=detections,
        detection_scope="last measured inference; confidence is a model score, not measured accuracy",
    )
    # Create a drawable three-channel copy without changing the inference input.
    annotated = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
    # Process each item in the selected collection.
    for item in detections:
        # Prepare x1, y1, x2, y2 for the next step using the values calculated so far.
        x1, y1, x2, y2 = item["box_xyxy"]
        # Call cv.rectangle for this step; its contract describes the result or side effect.
        cv.rectangle(annotated, (x1, y1), (x2 - 1, y2 - 1), (0, 255, 0), 2)
        # Prepare text for the next step using the values calculated so far.
        text = f"{item['label']} {item['confidence']:.2f}"
        # Call cv.putText for this step; its contract describes the result or side effect.
        cv.putText(
            annotated,
            text,
            (x1, max(18, y1 - 6)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
    # Create the explicit output/test directory using the existing overwrite policy.
    output.mkdir(parents=True, exist_ok=False)
    # Reject this invalid input before it can produce misleading output.
    if not cv.imwrite(str(output / "annotated.png"), annotated):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise OSError("Could not save annotated image; output directory may be partial")
    # Persist this explicitly requested local output; raw artifacts stay outside Git.
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    # Explain the current result, progress or failure in the terminal.
    print(f"Saved {len(detections)} detections to {args.output}/annotated.png")
    # Process each (key, values) in the selected collection.
    for key, values in report["timings"].items():
        # Explain the current result, progress or failure in the terminal.
        print(
            f"{key}: median {values['median_ms']:.2f} ms; p95 {values['p95_ms']:.2f} ms"
        )
    # Explain the current result, progress or failure in the terminal.
    print(f"Report: {args.output}/report.json")
    # Explain the current result, progress or failure in the terminal.
    print(
        "Same-image CPU compute only; this is not live FPS or camera-to-screen latency."
    )


def positive_int(value: str) -> int:
    """Parse a positive run count or thread-count option.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        int: Positive integer, or a conversion/argparse error.
    """
    # Convert command-line or parsed input to a number before validating its allowed range.
    number = int(value)
    # Reject this invalid input before it can produce misleading output.
    if number <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise argparse.ArgumentTypeError("must be a positive integer")
    # Return the documented result to the caller without starting another operation.
    return number


def confidence(value: str) -> float:
    """Parse a finite detector score threshold in the inclusive zero-to-one interval.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        float: Valid threshold; rejects nonfinite and out-of-range values.
    """
    # Convert command-line or parsed input to a number before validating its allowed range.
    number = float(value)
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(number) or not 0 <= number <= 1:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    # Return the documented result to the caller without starting another operation.
    return number


def main(argv: Sequence[str] | None = None) -> None:
    """Parse a saved-image benchmark request and load the optional OpenCV runtime.

    Args:
        argv (Sequence[str] | None): Command-line tokens, or None to parse the current
            process arguments.

    Returns:
        None: None on success; argparse exits with clear runtime/input errors.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare --image with its existing default, validation and help text.
    parser.add_argument("--image", type=Path, required=True)
    # Declare --prototxt with its existing default, validation and help text.
    parser.add_argument(
        "--prototxt", type=Path, default=Path("models/mobilenet-ssd/deploy.prototxt")
    )
    # Declare --weights with its existing default, validation and help text.
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("models/mobilenet-ssd/mobilenet_iter_73000.caffemodel"),
    )
    # Declare --output with its existing default, validation and help text.
    parser.add_argument("--output", type=Path, required=True)
    # Declare --threshold with its existing default, validation and help text.
    parser.add_argument("--threshold", type=confidence, default=0.5)
    # Declare --threads with its existing default, validation and help text.
    parser.add_argument("--threads", type=positive_int, default=2)
    # Declare --warmup with its existing default, validation and help text.
    parser.add_argument("--warmup", type=positive_int, default=3)
    # Declare --runs with its existing default, validation and help text.
    parser.add_argument("--runs", type=positive_int, default=20)
    # Declare --notes with its existing default, validation and help text.
    parser.add_argument(
        "--notes", default="Scene, lighting, cooling and power not supplied"
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args(argv)
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Load optional OpenCV only for detection or its explicit runtime test.
        import cv2
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except ImportError:
        # Call parser.exit for this step; its contract describes the result or side effect.
        parser.exit(
            1,
            "OpenCV (cv2) is missing or cannot import; see docs/DETECTION_BASELINE.md\n",
        )
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Call run for this step; its contract describes the result or side effect.
        run(args, cv2)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        # Call parser.exit for this step; its contract describes the result or side effect.
        parser.exit(1, f"Detection failed: {error}\n")


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call main for this step; its contract describes the result or side effect.
    main()
