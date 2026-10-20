"""Bounded, hardware-free appearance memory for experimental re-identification.

The coarse descriptor below crops grayscale frames without storing images.
The memory accepts normalized descriptors and never claims verified identity.
Live tracking enables this path only with ``--reidentify``; image motion and
IMU evidence are not part of the appearance decision.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


def grayscale_grid_descriptor(
    pixels: bytes, width: int, height: int, box_xyxy: Sequence[float],
) -> tuple[float, ...] | None:
    """Describe coarse grayscale layout inside a source-coordinate detection box.

    Args:
        pixels (bytes): Complete row-major uint8 grayscale source frame.
        width (int): Source width in pixels, normally 1280.
        height (int): Source height in pixels, normally 720.
        box_xyxy (Sequence[float]): Left, top, right, bottom source pixels.

    Returns:
        tuple[float, ...] | None: Mean-centered unit vector of 8×8 cell
        intensities, or None for a tiny, flat or invalid crop. This is a
        provisional experiment descriptor, not a trained identity embedding.
    """
    import numpy as np

    if width < 1 or height < 1 or len(pixels) != width * height:
        raise ValueError("Expected one complete grayscale source frame")
    if len(box_xyxy) != 4 or not all(math.isfinite(x) for x in box_xyxy):
        return None
    left = max(0, min(width, math.floor(box_xyxy[0])))
    top = max(0, min(height, math.floor(box_xyxy[1])))
    right = max(0, min(width, math.ceil(box_xyxy[2])))
    bottom = max(0, min(height, math.ceil(box_xyxy[3])))
    if right - left < 16 or bottom - top < 16:
        return None
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width)
    crop = image[top:bottom, left:right]
    if float(crop.std()) < 5:
        return None

    # Pool spatial brightness into fixed-size cells so source box size does
    # not change descriptor length. Centering removes overall exposure level.
    ys = np.linspace(0, crop.shape[0], 9, dtype=int)
    xs = np.linspace(0, crop.shape[1], 9, dtype=int)
    cells = [float(crop[ys[y]:ys[y + 1], xs[x]:xs[x + 1]].mean())
             for y in range(8) for x in range(8)]
    mean = sum(cells) / len(cells)
    centered = [value - mean for value in cells]
    if math.sqrt(sum(value * value for value in centered)) < 1:
        return None
    return normalize_descriptor(centered)


@dataclass(frozen=True)
class MemoryEntry:
    """One retired session ID with a normalized descriptor, not raw pixels."""

    track_id: int
    class_id: int
    descriptor: tuple[float, ...]
    seen_at: float


def normalize_descriptor(values: Sequence[float]) -> tuple[float, ...]:
    """Validate and unit-normalize one compact appearance vector.

    Args:
        values (Sequence[float]): One to 256 finite numeric descriptor values.

    Returns:
        tuple[float, ...]: Unit-length vector for cosine comparison.

    Raises:
        ValueError: The descriptor is empty, too large, invalid or all zero.
    """
    if not 1 <= len(values) <= 256:
        raise ValueError("Descriptor must have 1–256 values")
    if any(isinstance(value, bool) for value in values):
        raise ValueError("Descriptor values must be numeric, not boolean")
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError("Descriptor values must be numeric") from error
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("Descriptor values must be finite")
    length = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(length) or length == 0:
        raise ValueError("Descriptor must have nonzero finite length")
    return tuple(value / length for value in vector)


class RetiredObjectMemory:
    """Keep a bounded set of retired IDs and abstain on weak or tied matches."""

    def __init__(self, *, capacity: int, retention_s: float) -> None:
        """Set explicit limits without implying a calibrated production policy.

        Args:
            capacity (int): Maximum stored retired IDs.
            retention_s (float): Maximum seconds since an object's last sighting.
        """
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if not math.isfinite(retention_s) or retention_s <= 0:
            raise ValueError("retention_s must be positive and finite")
        self.capacity = capacity
        self.retention_s = float(retention_s)
        self._entries: dict[int, MemoryEntry] = {}
        self._last_now: float | None = None

    def __len__(self) -> int:
        """Return the number of stored retired IDs before the next expiry check."""
        return len(self._entries)

    def _advance(self, now: float) -> None:
        """Expire old entries using one nondecreasing host-monotonic clock.

        Args:
            now (float): Current host-monotonic time in seconds.
        """
        if not math.isfinite(now) or now < 0:
            raise ValueError("now must be finite and nonnegative")
        if self._last_now is not None and now < self._last_now:
            raise ValueError("Memory clock moved backwards")
        self._last_now = now
        for track_id, entry in list(self._entries.items()):
            if now - entry.seen_at > self.retention_s:
                del self._entries[track_id]

    def remember(
        self, track_id: int, class_id: int, descriptor: Sequence[float],
        *, seen_at: float, now: float,
    ) -> bool:
        """Store a retired ID if it is still within the explicit age limit.

        Args:
            track_id (int): Positive ID assigned earlier in this tracker run.
            class_id (int): Detector category number.
            descriptor (Sequence[float]): Compact vector, never a raw image crop.
            seen_at (float): Monotonic time of the object's last actual detection.
            now (float): Current monotonic time when retirement is processed.

        Returns:
            bool: Whether the entry was stored; already-expired entries return False.
        """
        if isinstance(track_id, bool) or not isinstance(track_id, int) or track_id < 1:
            raise ValueError("track_id must be a positive integer")
        if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id < 0:
            raise ValueError("class_id must be a nonnegative integer")
        if not math.isfinite(seen_at) or seen_at < 0 or seen_at > now:
            raise ValueError("seen_at must be finite and no later than now")
        normalized = normalize_descriptor(descriptor)
        self._advance(now)
        if now - seen_at > self.retention_s:
            return False

        # A duplicate ID updates one entry; capacity evicts the oldest sighting.
        self._entries[track_id] = MemoryEntry(track_id, class_id, normalized, seen_at)
        if len(self._entries) > self.capacity:
            oldest_id = min(self._entries, key=lambda ident: (
                self._entries[ident].seen_at, ident
            ))
            del self._entries[oldest_id]
        return True

    def take_match(
        self, class_id: int, descriptor: Sequence[float], *, now: float,
        min_similarity: float, min_margin: float,
    ) -> tuple[int, float] | None:
        """Claim one same-class old ID only if its cosine score is unambiguous.

        Args:
            class_id (int): Category of a current, otherwise-unmatched detection.
            descriptor (Sequence[float]): Current compact appearance vector.
            now (float): Current monotonic seconds, not a camera exposure time.
            min_similarity (float): Explicit score floor in [-1, 1].
            min_margin (float): Positive gap required over the runner-up score.

        Returns:
            tuple[int, float] | None: Claimed old ID and score, or no match.
            A claim consumes the ID so another detection cannot inherit it.
        """
        if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id < 0:
            raise ValueError("class_id must be a nonnegative integer")
        if not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1:
            raise ValueError("min_similarity must be finite and in [-1, 1]")
        if not math.isfinite(min_margin) or not 0 < min_margin <= 2:
            raise ValueError("min_margin must be finite and in (0, 2]")
        current = normalize_descriptor(descriptor)
        self._advance(now)

        # Different descriptor versions (lengths) and detector classes cannot
        # compete. Ranking alone never proves identity; weak/tied scores abstain.
        ranked = sorted(
            (
                (sum(a * b for a, b in zip(current, entry.descriptor)), entry.track_id)
                for entry in self._entries.values()
                if entry.class_id == class_id and len(entry.descriptor) == len(current)
            ),
            reverse=True,
        )
        if not ranked or ranked[0][0] < min_similarity:
            return None
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < min_margin:
            return None
        score, track_id = ranked[0]
        del self._entries[track_id]
        return track_id, score
