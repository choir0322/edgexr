"""Explicitly bounded process-RAM alternative to buffered profiler sample writes."""

from pathlib import Path
from typing import TextIO
import time


class SampleSink:
    """Keep ordered JSONL bytes in RAM or use the existing buffered file path."""

    def __init__(self, path: Path, mode: str, limit_bytes: int) -> None:
        """Create a fresh destination without silently falling back to disk.

        Args:
            path (Path): Final samples.jsonl, absent before collection.
            mode (str): 'file' or 'ram'; RAM is ordinary pageable process memory.
            limit_bytes (int): Maximum accepted UTF-8 payload bytes in RAM mode.
        Returns:
            None: RAM mode does not create the destination file yet.
        """
        if mode not in ("file", "ram") or limit_bytes <= 0:
            raise ValueError("Invalid sample sink mode or capacity")
        if path.exists():
            raise FileExistsError(path)
        self.path, self.mode, self.limit_bytes = path, mode, limit_bytes
        self.chunks: list[bytes] = []
        self.payload_bytes = 0
        self.rows = 0
        self.overflow = False
        self.closed = False
        self.file: TextIO | None = path.open("x", encoding="utf-8") if mode == "file" else None

    def write(self, text: str) -> int:
        """Admit one complete serialized row, with no spill or silent drop.

        Args:
            text (str): JSONL produced by the observer's existing serializer.
        Returns:
            int: Characters accepted; BufferError rejects the entire new row.
        """
        if self.closed:
            raise ValueError("Sample sink is closed")
        payload = text.encode("utf-8")
        if self.mode == "ram":
            if self.payload_bytes + len(payload) > self.limit_bytes:
                self.overflow = True
                raise BufferError("RAM sample payload cap reached; no disk spill")
            if payload:
                self.chunks.append(payload)
        else:
            self.file.write(text)
        self.payload_bytes += len(payload)
        self.rows += 1
        return len(text)

    def close(self) -> None:
        """Close collection; retain RAM chunks for a subsequent explicit export.

        Args: None.
        Returns:
            None: File mode flushes its existing buffered file; RAM does no I/O.
        """
        self.closed = True
        if self.file is not None:
            self.file.close()

    def describe(self) -> dict:
        """Return admitted-byte accounting without estimating total RSS.

        Args: None.
        Returns:
            dict: Mode, counts, payload cap, overflow and memory limitations.
        """
        return {"mode": self.mode, "accepted_rows": self.rows,
                "payload_bytes": self.payload_bytes,
                "ram_payload_limit_bytes": self.limit_bytes if self.mode == "ram" else None,
                "overflow": self.overflow,
                "scope": "Payload bound excludes Python objects, current serialization and app memory. RAM is pageable, volatile and not mlocked."}

    def export(self) -> dict:
        """Stream closed RAM chunks after collection, without overwriting evidence.

        Args: None.
        Returns:
            dict: Export status/timings; failure preserves partial output and RAM.
        """
        if not self.closed:
            raise ValueError("Close collection before exporting")
        if self.mode == "file":
            return {"status": "not_needed"}
        start, cpu = time.monotonic(), time.process_time()
        partial = self.path.with_suffix(".jsonl.partial")
        result = {"started_host_s": start, "bytes": 0, "partial_path": str(partial)}
        try:
            if self.path.exists():
                raise FileExistsError(self.path)
            with partial.open("xb") as target:
                for chunk in self.chunks:
                    target.write(chunk)
                    result["bytes"] += len(chunk)
            # Hard link is a no-overwrite publication on the same filesystem.
            self.path.hardlink_to(partial)
            partial.unlink()
            result["status"] = "complete"
            self.chunks.clear()
        except (OSError, KeyboardInterrupt) as error:
            result.update(status="failed", error=str(error) or "export interrupted")
        end = time.monotonic()
        result.update(finished_host_s=end, wall_s=end - start,
                      cpu_s=time.process_time() - cpu,
                      durability="Buffered export; no fsync/power-loss guarantee")
        return result
