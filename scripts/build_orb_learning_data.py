"""Generate small ORB replay data from already-public learning images; no capture."""

from __future__ import annotations

import json
from pathlib import Path
import cv2 as cv
import numpy as np
from spatial.scene_memory import MemoryConfig, SceneMemory, prepare_gray


def example(reference_path: Path, query_path: Path) -> dict:
    """Extract actual features/matches and retain the production decision.

    Args:
        reference_path (Path): Existing public grayscale learning image.
        query_path (Path): Existing public query image.
    Returns:
        dict: JSON-compatible canonical points, matches, descriptors and decision.
    """
    config = MemoryConfig()
    original_a = cv.imread(str(reference_path), cv.IMREAD_GRAYSCALE)
    original_b = cv.imread(str(query_path), cv.IMREAD_GRAYSCALE)
    a, b = prepare_gray(cv, original_a), prepare_gray(cv, original_b)
    orb = cv.ORB_create(nfeatures=config.max_features)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    pa = np.float32([k.pt for k in ka])
    pb = np.float32([k.pt for k in kb])
    matcher = cv.BFMatcher(cv.NORM_HAMMING)
    reverse = {m.queryIdx: m.trainIdx for m in matcher.match(db, da)}
    pairs = []
    for best, second in matcher.knnMatch(da, db, k=2):
        mutual = reverse.get(best.trainIdx) == best.queryIdx
        accepted = best.distance <= config.max_hamming and best.distance < config.ratio * second.distance and mutual
        pairs.append({"a": best.queryIdx, "b": best.trainIdx, "d1": best.distance,
                      "d2": second.distance, "mutual": mutual, "accepted": accepted,
                      "inlier": False})
    good = [p for p in pairs if p["accepted"]]
    homography = None
    hulls = [[], []]
    if len(good) >= config.min_matches:
        source = np.float32([pa[p["a"]] for p in good])
        target = np.float32([pb[p["b"]] for p in good])
        cv.setRNGSeed(0)
        homography, mask = cv.findHomography(source, target, cv.RANSAC,
                                             config.reprojection_pixels,
                                             maxIters=2000, confidence=0.995)
        if mask is not None:
            for p, flag in zip(good, mask.ravel()):
                p["inlier"] = bool(flag)
            selected = mask.ravel().astype(bool)
            hulls = [cv.convexHull(points[selected]).reshape(-1, 2).tolist()
                     for points in (source, target)]
    # Production decides; the parallel intermediate extraction is checked against
    # its counts so a teaching illustration cannot silently invent an outcome.
    memory = SceneMemory(cv=cv)
    enrollment = memory.process(original_a, 0, "Reference A")
    cv.setRNGSeed(0)
    decision = memory.process(original_b, 1)
    candidate = decision["candidates"][0]
    assert candidate["matches"] == len(good)
    assert candidate["inliers"] == sum(p["inlier"] for p in good)
    chosen = next((p for p in good if p["inlier"]), pairs[0])
    return {"reference": reference_path.name, "query": query_path.name,
            "original_shapes": [list(original_a.shape), list(original_b.shape)],
            "points_a": pa.round(3).tolist(), "points_b": pb.round(3).tolist(),
            "pairs": pairs, "selected": chosen,
            "bits_a": np.unpackbits(da[chosen["a"]]).tolist(),
            "bits_b": np.unpackbits(db[chosen["b"]]).tolist(),
            "homography": homography.tolist() if homography is not None else None,
            "hulls": hulls, "enrollment": enrollment, "decision": decision}


def main() -> None:
    """Regenerate the browser's replay arrays, without model or video dependencies.

    Args: None.
    Returns: None; writes a derived JS asset in docs/learning/images.
    """
    cv.setNumThreads(1)
    root = Path(__file__).resolve().parents[1] / "docs/learning/images"
    data = {"opencv": cv.__version__, "settings": SceneMemory(cv=cv).settings(),
            "scope": "Offline ORB replay; existing 320x180 Pi frame enlarged to canonical 640x360, not new 720p evidence; foreground exclusion off.",
            "examples": [example(root / "hann-frame-313.png", root / name)
                         for name in ("hann-frame-314.png", "detection-lesson-scene.png")]}
    (root / "orb-scene-data.js").write_text("window.ORB_DATA=" + json.dumps(data, separators=(",", ":")) + ";\n")
    print([(e["query"], e["decision"]["state"], e["decision"]["candidates"][0]["matches"]) for e in data["examples"]])


if __name__ == "__main__":
    main()
