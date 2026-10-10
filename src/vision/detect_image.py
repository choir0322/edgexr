"""Measure MobileNet-SSD on one saved monochrome image; no camera or downloads."""

from __future__ import annotations
from typing import Any, Iterable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from _contracts import Record


import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time


# Class IDs are fixed by this pretrained VOC model: background plus 20 objects.
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
    # Validate the image dimensions and SSD row contract before interpreting IDs
    # or scores; the sentinel is a valid no-detection response.
    if width <= 0 or height <= 0 or not 0 <= threshold <= 1:
        raise ValueError("Invalid image dimensions or confidence threshold")
    detections = []
    for row in rows:
        if len(row) != 7 or not all(math.isfinite(float(v)) for v in row):
            raise ValueError("Expected finite SSD rows of seven values")
        batch, label, score, left, top, right, bottom = map(float, row)
        if batch == -1:  # SSD may use a sentinel when no detections exist.
            continue
        if batch != 0 or label != int(label) or not 0 <= label < len(LABELS):
            raise ValueError("Unexpected batch or class ID; check model files")
        if not 0 <= score <= 1:
            raise ValueError("Invalid detection confidence")

        # Discard background/low scores, clamp normalized coordinates to the image,
        # and round outward to pixel boundaries. Ignore boxes with no positive area.
        if label == 0 or score < threshold:
            continue
        x1 = math.floor(max(0, min(1, left)) * width)
        y1 = math.floor(max(0, min(1, top)) * height)
        x2 = math.ceil(max(0, min(1, right)) * width)
        y2 = math.ceil(max(0, min(1, bottom)) * height)
        if x2 <= x1 or y2 <= y1:
            continue
        detections.append(
            dict(
                class_id=int(label),
                label=LABELS[int(label)],
                confidence=score,
                box_xyxy=[x1, y1, x2, y2],
            )
        )
    return detections


def timing_summary(values: Sequence[float]) -> dict[str, float]:
    """Summarize finite nonnegative compute-duration measurements.

    Args:
        values (Sequence[float]): Nonnegative elapsed durations in milliseconds; at
            least one value.

    Returns:
        dict[str, float]: Median, nearest-rank p95, minimum and maximum in milliseconds.
    """
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Timing samples must be finite and nonnegative")

    # Summarize elapsed milliseconds with a nearest-rank p95, not interpolation.
    ordered = sorted(values)
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
    # Replicate gray into three channels and construct the expected 300×300 tensor.
    # (pixel − 127.5) × 0.007843 is approximately continuous [-1, 1], not three values.
    start = time.perf_counter_ns()
    bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
    blob = cv.dnn.blobFromImage(
        bgr,
        scalefactor=0.007843,
        size=(300, 300),
        mean=(127.5, 127.5, 127.5),
        swapRB=False,
        crop=False,
    )
    prepared = time.perf_counter_ns()

    # Time inference separately from preprocessing, then validate the SSD output
    # shape before callers parse boxes or benchmark postprocessing.
    net.setInput(blob)
    output = net.forward()
    inferred = time.perf_counter_ns()
    if output.ndim != 4 or output.shape[:2] != (1, 1) or output.shape[-1] != 7:
        raise ValueError("Expected SSD output [1, 1, N, 7]; check model files")
    return output[0, 0], start, prepared, inferred


def sha256(path: Path) -> str:
    """Hash an input or model artifact incrementally for reproducibility.

    Args:
        path (Path): Local filesystem path read by this operation.

    Returns:
        str: Lowercase SHA-256 hex digest; filesystem errors propagate.
    """
    # Hash the file in bounded chunks so large model weights need not fit in memory.
    digest = hashlib.sha256()
    with path.open("rb") as handle:

        def read_hash_block() -> bytes:
            """Read the next one-megabyte hash block; empty bytes signal end of file.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                bytes: The callback result described above.
            """
            return handle.read(1024 * 1024)

        for block in iter(read_hash_block, b""):
            digest.update(block)
    return digest.hexdigest()


def cpu_temperature() -> float | None:
    """Read the conventional Pi thermal-zone temperature when available.

    Args:
        None.

    Returns:
        float | None: Degrees Celsius, or None if the interface is absent or unreadable.
    """
    try:
        return float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def git_info() -> Record:
    """Record repository revision and dirty state without changing Git.

    Args:
        None.

    Returns:
        Record: Revision/dirty fields, or None values when Git information is
            unavailable.
    """
    # Record code provenance when Git is available; unavailable is distinct from
    # a clean working tree and must not be reported as a known revision.
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return dict(revision=revision, dirty=bool(dirty))
    except (OSError, subprocess.CalledProcessError):
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
    # Require existing input/model files and a new output beneath recordings/.
    # Never overwrite a previous experiment or silently obtain model artifacts.
    output = args.output.resolve()
    if not output.is_relative_to(Path("recordings").resolve()) or output.exists():
        raise ValueError(
            "Choose a NEW directory inside recordings/; run from repo root"
        )
    for path in (args.image, args.prototxt, args.weights):
        if not path.is_file():
            raise ValueError(f"Missing file: {path}; see docs/DETECTION_BASELINE.md")
    import numpy as np

    # Decode the image once and load the CPU model with explicit thread settings.
    # Model-loading time is recorded separately from per-inference measurements.
    gray = cv.imread(str(args.image), cv.IMREAD_GRAYSCALE)
    if gray is None or gray.size == 0:
        raise ValueError("Could not decode the input image")
    height, width = gray.shape
    cv.setNumThreads(args.threads)
    cv.ocl.setUseOpenCL(False)
    start = time.perf_counter_ns()
    net = cv.dnn.readNetFromCaffe(str(args.prototxt), str(args.weights))
    net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)
    load_ms = (time.perf_counter_ns() - start) / 1e6

    # Warm up on the same image, then retain only measured iterations. Separate
    # preprocessing, inference and parsing durations; sample temperature around the run.
    before = cpu_temperature()
    timings = []
    for index in range(args.warmup + args.runs):
        rows, started, prepared, inferred = infer_once(cv, net, gray)
        detections = parse_detections(rows, width, height, args.threshold)
        finished = time.perf_counter_ns()
        if index >= args.warmup:
            timings.append(
                dict(
                    preprocess_ms=(prepared - started) / 1e6,
                    inference_ms=(inferred - prepared) / 1e6,
                    postprocess_ms=(finished - inferred) / 1e6,
                    total_ms=(finished - started) / 1e6,
                )
            )
    after = cpu_temperature()

    # Assemble reproducibility metadata, timing summaries and the final predictions.
    # These measurements exclude capture/display and are not live frame rate.
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

    # Draw final source-coordinate boxes and labels outside the timed region;
    # right/bottom bounds are exclusive when passed to the rectangle renderer.
    annotated = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
    for item in detections:
        x1, y1, x2, y2 = item["box_xyxy"]
        cv.rectangle(annotated, (x1, y1), (x2 - 1, y2 - 1), (0, 255, 0), 2)
        text = f"{item['label']} {item['confidence']:.2f}"
        cv.putText(
            annotated,
            text,
            (x1, max(18, y1 - 6)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    # Create the output only after computation, save image/report, then report
    # compute statistics without implying measured detection accuracy.
    output.mkdir(parents=True, exist_ok=False)
    if not cv.imwrite(str(output / "annotated.png"), annotated):
        raise OSError("Could not save annotated image; output directory may be partial")
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(f"Saved {len(detections)} detections to {args.output}/annotated.png")
    for key, values in report["timings"].items():
        print(
            f"{key}: median {values['median_ms']:.2f} ms; p95 {values['p95_ms']:.2f} ms"
        )
    print(f"Report: {args.output}/report.json")
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
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def confidence(value: str) -> float:
    """Parse a finite detector score threshold in the inclusive zero-to-one interval.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        float: Valid threshold; rejects nonfinite and out-of-range values.
    """
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def main(argv: Sequence[str] | None = None) -> None:
    """Parse a saved-image benchmark request and load the optional OpenCV runtime.

    Args:
        argv (Sequence[str] | None): Command-line tokens, or None to parse the current
            process arguments.

    Returns:
        None: None on success; argparse exits with clear runtime/input errors.
    """
    # Define and parse image/model paths, benchmark counts and CPU settings.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--prototxt", type=Path, default=Path("models/mobilenet-ssd/deploy.prototxt")
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("models/mobilenet-ssd/mobilenet_iter_73000.caffemodel"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=confidence, default=0.5)
    parser.add_argument("--threads", type=positive_int, default=2)
    parser.add_argument("--warmup", type=positive_int, default=3)
    parser.add_argument("--runs", type=positive_int, default=20)
    parser.add_argument(
        "--notes", default="Scene, lighting, cooling and power not supplied"
    )
    args = parser.parse_args(argv)

    # Import the optional runtime only when executing detection, and turn expected
    # setup/inference failures into a concise command-line error.
    try:
        import cv2
    except ImportError:
        parser.exit(
            1,
            "OpenCV (cv2) is missing or cannot import; see docs/DETECTION_BASELINE.md\n",
        )
    try:
        run(args, cv2)
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        parser.exit(1, f"Detection failed: {error}\n")


if __name__ == "__main__":
    main()
