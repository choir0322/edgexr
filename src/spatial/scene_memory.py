"""Bounded, session-local visual view recognition; no camera pose or object IDs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np


WIDTH, HEIGHT = 640, 360


@dataclass(frozen=True)
class MemoryConfig:
    """Experimental thresholds in 640×360 image pixels, not probabilities."""

    max_views: int = 12
    max_features: int = 600
    min_features: int = 60
    ratio: float = 0.75
    max_hamming: int = 64
    min_matches: int = 24
    min_inliers: int = 20
    min_inlier_ratio: float = 0.55
    min_coverage: float = 0.12
    min_cells: int = 4
    reprojection_pixels: float = 3.0
    ambiguity_ratio: float = 0.85


@dataclass
class View:
    """One explicit reference: bounded ORB coordinates/descriptors, no raw image."""

    scene_id: int
    label: str
    observed_s: float
    last_used_s: float
    points: np.ndarray
    descriptors: np.ndarray


def prepare_gray(cv: Any, image: np.ndarray) -> np.ndarray:
    """Validate and resize an existing grayscale frame for feature extraction.

    Args:
        cv (Any): Installed OpenCV module.
        image (np.ndarray): Nonempty 16:9 uint8 grayscale input, at least 160×90.
    Returns:
        np.ndarray: 360×640 uint8 grayscale image.
    """
    if (image.ndim != 2 or image.dtype != np.uint8 or
            image.shape[0] < 90 or image.shape[1] < 160 or
            abs(image.shape[1] / image.shape[0] - 16 / 9) > 0.01):
        raise ValueError("Scene input must be uint8 16:9 grayscale, at least 160×90")
    interpolation = cv.INTER_AREA if image.shape[1] >= WIDTH else cv.INTER_LINEAR
    return cv.resize(image, (WIDTH, HEIGHT), interpolation=interpolation)


def spatial_support(cv: Any, points: np.ndarray) -> tuple[float, int]:
    """Measure how widely matching features cover a canonical frame.

    Args:
        cv (Any): OpenCV module used for convex-hull area.
        points (np.ndarray): N×2 float image coordinates in 640×360 pixels.
    Returns:
        tuple[float, int]: Hull area divided by frame area and occupied 3×3 cells.
    """
    if len(points) < 3:
        return 0.0, 0
    coverage = float(cv.contourArea(cv.convexHull(points.astype(np.float32)))) / (WIDTH * HEIGHT)
    cells = {(min(2, max(0, int(x * 3 / WIDTH))), min(2, max(0, int(y * 3 / HEIGHT))))
             for x, y in points}
    return coverage, len(cells)


def verify_view(cv: Any, reference: View, points: np.ndarray,
                descriptors: np.ndarray, config: MemoryConfig) -> dict:
    """Compare a query to one reference using descriptor and geometric evidence.

    Args:
        cv (Any): OpenCV module; ORB descriptors use NORM_HAMMING.
        reference (View): Previously enrolled features in canonical coordinates.
        points (np.ndarray): Query feature positions, N×2 float32.
        descriptors (np.ndarray): Query ORB descriptors, N×32 uint8.
        config (MemoryConfig): Experimental matching/geometry thresholds.
    Returns:
        dict: Candidate diagnostics, accepted flag and rejection reason; no confidence probability.
    """
    result = {"scene_id": reference.scene_id, "label": reference.label,
              "accepted": False, "reason": "few_matches", "matches": 0,
              "inliers": 0, "inlier_ratio": 0.0}
    if min(len(reference.descriptors), len(descriptors)) < 2:
        return result

    # Ratio filtering rejects ambiguous descriptors. Mutual nearest neighbors
    # enforce one-to-one correspondence before estimating reference→query geometry.
    matcher = cv.BFMatcher(cv.NORM_HAMMING)
    pairs = matcher.knnMatch(reference.descriptors, descriptors, k=2)
    reverse = {match.queryIdx: match.trainIdx
               for match in matcher.match(descriptors, reference.descriptors)}
    good = []
    for pair in pairs:
        if len(pair) != 2:
            continue
        best, second = pair
        if (best.distance <= config.max_hamming and
                best.distance < config.ratio * second.distance and
                reverse.get(best.trainIdx) == best.queryIdx):
            good.append(best)
    result["matches"] = len(good)
    if len(good) < config.min_matches:
        return result
    source = np.float32([reference.points[match.queryIdx] for match in good])
    target = np.float32([points[match.trainIdx] for match in good])
    homography, mask = cv.findHomography(source, target, cv.RANSAC,
                                         config.reprojection_pixels,
                                         maxIters=2000, confidence=0.995)
    result["reason"] = "invalid_geometry"
    if homography is None or mask is None or not np.isfinite(homography).all():
        return result
    inliers = mask.ravel().astype(bool)
    count = int(inliers.sum())
    result.update(inliers=count, inlier_ratio=count / len(good))
    if count < config.min_inliers or count / len(good) < config.min_inlier_ratio:
        result["reason"] = "few_geometric_inliers"
        return result

    # A small foreground patch should not establish a whole-view revisit. Demand
    # support spread across both frames, plus a finite, nonfolding image footprint.
    source_coverage, source_cells = spatial_support(cv, source[inliers])
    target_coverage, target_cells = spatial_support(cv, target[inliers])
    result.update(reference_coverage=source_coverage, query_coverage=target_coverage,
                  reference_cells=source_cells, query_cells=target_cells)
    if (min(source_coverage, target_coverage) < config.min_coverage or
            min(source_cells, target_cells) < config.min_cells):
        result["reason"] = "concentrated_support"
        return result
    corners = np.float32([[0, 0], [WIDTH, 0], [WIDTH, HEIGHT], [0, HEIGHT]])
    projected = np.column_stack((corners, np.ones(4))) @ homography.T
    denominators = projected[:, 2]
    if (np.any(np.abs(denominators) < 1e-8) or
            not (np.all(denominators > 0) or np.all(denominators < 0))):
        return result
    footprint = (projected[:, :2] / denominators[:, None]).astype(np.float32)
    area = float(cv.contourArea(footprint, oriented=True)) / (WIDTH * HEIGHT)
    if (not np.isfinite(footprint).all() or not cv.isContourConvex(footprint) or
            not 0.25 <= area <= 4.0):
        return result
    result.update(accepted=True, reason="geometry_verified", footprint_area_ratio=area)
    return result


class SceneMemory:
    """Single-owner bounded view memory; enrollment is explicit, queries are conservative."""

    def __init__(self, config: MemoryConfig | None = None, cv: Any = None) -> None:
        """Create feature extraction and an empty reference set.

        Args:
            config (MemoryConfig | None): Thresholds or defaults.
            cv (Any): Optional installed OpenCV module; loaded lazily if omitted.
        Returns:
            None: No hardware, model download or image capture occurs.
        """
        if cv is None:
            import cv2 as cv
        self.cv = cv
        self.config = config or MemoryConfig()
        c = self.config
        if (not 1 <= c.max_views <= 30 or not 60 <= c.max_features <= 2000 or
                not 4 <= c.min_inliers <= c.min_matches <= c.min_features <= c.max_features or
                not 0 < c.ratio < 1 or not 0 < c.ambiguity_ratio <= 1 or
                not 0 < c.min_inlier_ratio <= 1 or not 0 < c.min_coverage <= 1 or
                not 1 <= c.min_cells <= 9 or not 0 < c.max_hamming <= 256 or
                not math.isfinite(c.reprojection_pixels) or c.reprojection_pixels <= 0):
            raise ValueError("Invalid scene-memory limits or thresholds")
        self.orb = cv.ORB_create(nfeatures=c.max_features)
        self.views: list[View] = []
        self.next_id = 1
        self.last_time: float | None = None

    def process(self, gray: np.ndarray, timestamp_s: float,
                enroll_label: str | None = None) -> dict:
        """Enroll a named reference or query previous views at a later video time.

        Args:
            gray (np.ndarray): 16:9 uint8 grayscale frame from a local decoder.
            timestamp_s (float): Finite nonnegative video time, strictly increasing.
            enroll_label (str | None): Explicit unique reference name; None queries memory.
        Returns:
            dict: enrolled/known/unknown state, scene ID, reasons and bounded diagnostics.
        """
        if (not math.isfinite(timestamp_s) or timestamp_s < 0 or
                (self.last_time is not None and timestamp_s <= self.last_time)):
            raise ValueError("Scene timestamps must be finite and strictly increasing")
        if enroll_label is not None and (not enroll_label.strip() or len(enroll_label) > 80 or
                any(view.label == enroll_label for view in self.views)):
            raise ValueError("Reference labels must be nonempty, unique and at most 80 characters")
        image = prepare_gray(self.cv, gray)
        keypoints, descriptors = self.orb.detectAndCompute(image, None)
        points = np.float32([point.pt for point in keypoints]).reshape(-1, 2)
        self.last_time = timestamp_s
        coverage, cells = spatial_support(self.cv, points)
        result = {"timestamp_s": timestamp_s, "state": "unknown", "scene_id": None,
                  "label": None, "reason": "weak_image", "features": len(points),
                  "candidates": [], "stored_views": len(self.views)}
        if (descriptors is None or len(points) < self.config.min_features or
                coverage < self.config.min_coverage or cells < self.config.min_cells):
            return result

        if enroll_label is not None:
            evicted = None
            if len(self.views) >= self.config.max_views:
                oldest = min(range(len(self.views)), key=self._recency)
                evicted = self.views.pop(oldest).scene_id
            view = View(self.next_id, enroll_label, timestamp_s, timestamp_s,
                        points.copy(), descriptors.copy())
            self.views.append(view)
            self.next_id += 1
            result.update(state="enrolled", scene_id=view.scene_id, label=view.label,
                          reason="explicit_reference", evicted_id=evicted,
                          stored_views=len(self.views))
            return result

        candidates = [verify_view(self.cv, view, points, descriptors, self.config)
                      for view in self.views]
        result["candidates"] = candidates
        accepted = sorted((candidate for candidate in candidates if candidate["accepted"]),
                          key=self._rank, reverse=True)
        result["reason"] = "no_verified_match" if self.views else "empty_memory"
        if not accepted:
            return result
        if (len(accepted) > 1 and accepted[1]["inliers"] >=
                accepted[0]["inliers"] * self.config.ambiguity_ratio):
            result["reason"] = "ambiguous_views"
            return result
        winner = accepted[0]
        for view in self.views:
            if view.scene_id == winner["scene_id"]:
                view.last_used_s = timestamp_s
        result.update(state="known", scene_id=winner["scene_id"], label=winner["label"],
                      reason="geometry_verified")
        return result

    def _recency(self, index: int) -> float:
        """Read reference recency for deterministic LRU eviction.

        Args:
            index (int): Index within the current bounded reference list.
        Returns:
            float: Last successful use or enrollment time in seconds.
        """
        return self.views[index].last_used_s

    @staticmethod
    def _rank(candidate: dict) -> tuple[int, float]:
        """Rank verified candidates by support, without claiming probability.

        Args:
            candidate (dict): Geometrically accepted comparison diagnostics.
        Returns:
            tuple[int, float]: Inlier count followed by inlier fraction.
        """
        return candidate["inliers"], candidate["inlier_ratio"]

    def reset(self) -> None:
        """Clear scene references and time origin, preserving monotonic scene IDs.

        Args:
            None.
        Returns:
            None: Later references cannot reuse an old scene ID in this instance.
        """
        self.views.clear()
        self.last_time = None

    def settings(self) -> dict:
        """Expose limits and units for a reproducible offline report.

        Args:
            None.
        Returns:
            dict: Configuration and canonical processing dimensions.
        """
        return {**asdict(self.config), "image_width": WIDTH, "image_height": HEIGHT}
