"""Bounded motion-pair history for estimating scene shift between frame times."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MotionPair:
    """One analyzed pair in the 320×180 image coordinate system."""

    first_seq: int
    first_time: float
    last_seq: int
    last_time: float
    shift: tuple[float, float] | None


class MotionHistory:
    """Keep recent pair shifts; return unknown for uncovered or unreliable time."""

    def __init__(self, limit: int = 180, max_pair_seconds: float = 0.12) -> None:
        """Bound the retained work and the length of an interpolated pair.

        Args:
            limit (int): Maximum analyzed pairs retained in chronological order.
            max_pair_seconds (float): Largest pair span allowed for interpolation.

        Returns:
            None: Initializes an empty history without starting a worker.
        """
        if limit < 1 or not math.isfinite(max_pair_seconds) or max_pair_seconds <= 0:
            raise ValueError("History limit and pair duration must be positive")
        self.max_pair_seconds = max_pair_seconds
        self.pairs: deque[MotionPair] = deque(maxlen=limit)

    def add(
        self,
        first_seq: int,
        first_time: float,
        last_seq: int,
        last_time: float,
        shift: tuple[float, float] | None,
    ) -> None:
        """Append a processed pair, retaining failed estimates as explicit gaps.

        Args:
            first_seq (int): Previous analyzed camera sequence.
            first_time (float): Previous host receipt time in monotonic seconds.
            last_seq (int): Current analyzed camera sequence.
            last_time (float): Current host receipt time in monotonic seconds.
            shift (tuple[float, float] | None): Scene dx/dy in 320×180 pixels,
                or no reliable estimate.

        Returns:
            None: Adds one bounded record; an implausibly long pair is unknown.
        """
        if (
            last_seq <= first_seq
            or not all(math.isfinite(t) for t in (first_time, last_time))
            or last_time <= first_time
        ):
            raise ValueError("Motion pairs must have increasing sequences and times")
        if self.pairs and (
            self.pairs[-1].last_seq != first_seq
            or self.pairs[-1].last_time != first_time
        ):
            self.pairs.clear()
        valid = (
            shift is not None
            and len(shift) == 2
            and all(math.isfinite(value) for value in shift)
            and last_time - first_time <= self.max_pair_seconds
        )
        self.pairs.append(
            MotionPair(first_seq, first_time, last_seq, last_time, shift if valid else None)
        )

    def displacement(self, start: float, end: float) -> tuple[float, float] | None:
        """Integrate scene shift across a fully covered host-time interval.

        Args:
            start (float): Older detector source receipt time, monotonic seconds.
            end (float): Newer detector source receipt time, monotonic seconds.

        Returns:
            tuple[float, float] | None: Estimated dx/dy in 320×180 pixels, or
                unknown. A detector timestamp inside an analyzed pair uses a
                linear fraction of that pair; this is an approximation, not
                exposure synchronization.
        """
        if not all(math.isfinite(t) for t in (start, end)) or end <= start:
            return None
        if not self.pairs or start < self.pairs[0].first_time or end > self.pairs[-1].last_time:
            return None

        # Walk only the overlapping pairs. Requiring continuous valid coverage
        # prevents an unknown segment from silently acting like zero movement.
        covered_until = start
        dx = dy = 0.0
        for pair in self.pairs:
            if pair.last_time <= start:
                continue
            if pair.first_time >= end:
                break
            overlap_start = max(start, pair.first_time)
            overlap_end = min(end, pair.last_time)
            if overlap_start > covered_until + 1e-9 or pair.shift is None:
                return None
            fraction = (overlap_end - overlap_start) / (pair.last_time - pair.first_time)
            dx += pair.shift[0] * fraction
            dy += pair.shift[1] * fraction
            covered_until = overlap_end
        return (dx, dy) if covered_until >= end - 1e-9 else None
