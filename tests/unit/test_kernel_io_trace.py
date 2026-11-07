"""Private ftrace lifecycle and loss/export checks using ordinary temporary files."""

import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from profiling.kernel_io_trace import (
    EVENTS, configure_instance, export_trace, loss_counts, run, select_events,
)


class KernelIoTraceTests(unittest.TestCase):
    def test_mmc_filter_is_exact_and_required_on_both_events(self) -> None:
        """Verify private host filtering, saved readback and fail-closed setup."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "events").mkdir()
            (root / "trace_clock").write_text("mono")
            (root / "buffer_total_size_kb").write_text("8192")
            events = ["mmc:mmc_request_start", "mmc:mmc_request_done"]
            for event in events:
                path = root / "events" / event.replace(":", "/")
                path.mkdir(parents=True)
                (path / "format").write_text("field:__data_loc char[] name;")
            result = configure_instance(root, events, 2048, "mmc0")
            self.assertEqual(result["event_filters"], {e: 'name == "mmc0"' for e in events})
            original_read = Path.read_text

            def wrong_filter(path: Path, *args: object, **kwargs: object) -> str:
                """Emulate a kernel returning an unapplied filter."""
                return "none" if path.name == "filter" else original_read(path, *args, **kwargs)

            with patch.object(Path, "read_text", wrong_filter):
                with self.assertRaisesRegex(ValueError, "readback mismatch"):
                    configure_instance(root, events, 2048, "mmc0")
            with self.assertRaisesRegex(ValueError, "both MMC"):
                configure_instance(root, events[:1], 2048, "mmc0")
            with self.assertRaisesRegex(ValueError, "exact name"):
                configure_instance(root, events, 2048, 'mmc0" || name != "')
            path = root / "events/mmc/mmc_request_start/format"
            path.write_text("field:int name;")
            with self.assertRaisesRegex(ValueError, "host string"):
                configure_instance(root, events, 2048, "mmc0")

    def test_required_events_and_missing_optional_are_explicit(self) -> None:
        """Fail before configuration without the essential target event groups.

        Args: None.
        Returns: None.
        """
        required = "block:block_rq_issue block:block_rq_complete jbd2:jbd2_lock_buffer_stall"
        events, missing = select_events(required)
        self.assertEqual(len(events), 3)
        self.assertIn("mmc:mmc_request_start", missing)
        with self.assertRaises(ValueError):
            select_events("block:block_rq_issue")

    def test_loss_and_export_boundaries(self) -> None:
        """Preserve loss and unavailable accounting; distinguish exact cap from clipping.

        Args: None.
        Returns: None.
        """
        value = loss_counts("entries: 80\noverrun: 5\ncommit overrun: 0\ndropped events: 2\n")
        self.assertTrue(value["all_available"])
        self.assertEqual(value["counters"]["overrun"], 5)
        self.assertFalse(loss_counts("entries: 80\n")["all_available"])
        for payload, clipped in ((b"1234", False), (b"12345", True)):
            output = io.BytesIO()
            result = export_trace(io.BytesIO(payload), output, 4)
            self.assertEqual(result, {"bytes": 4, "truncated": clipped})
            self.assertEqual(output.getvalue(), b"1234")

    def test_configure_only_instance_with_host_clock_and_memory_bound(self) -> None:
        """Require mono clock and save layouts without writing global tracer options.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            instance = root / "instances" / "owned"
            event = instance / "events/block/block_rq_issue"
            event.mkdir(parents=True)
            (root / "tracing_on").write_text("1")
            (instance / "trace_clock").write_text("[local] mono global")
            (instance / "buffer_total_size_kb").write_text("8192")
            (event / "format").write_text("field:dev_t dev;\n")
            result = configure_instance(instance, ["block:block_rq_issue"], 2048)
            self.assertEqual(result["buffer_total_kb"], 8192)
            self.assertIn("field:dev_t", result["event_formats"]["block:block_rq_issue"])
            self.assertEqual((root / "tracing_on").read_text(), "1")
            self.assertEqual((event / "enable").read_text(), "1\n")
            (instance / "trace_clock").write_text("[local] global")
            with self.assertRaisesRegex(ValueError, "mono"):
                configure_instance(instance, [], 2048)
            (instance / "trace_clock").write_text("mono")
            (instance / "buffer_total_size_kb").write_text("65536")
            with self.assertRaisesRegex(ValueError, "32 MiB"):
                configure_instance(instance, [], 2048)

    def test_existing_evidence_is_rejected_before_trace_access(self) -> None:
        """Never overwrite a previous trace folder, even when invoked with root.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "recordings" / "previous"
            output.mkdir(parents=True)
            with patch("profiling.kernel_io_trace.Path.cwd", return_value=root), patch("profiling.kernel_io_trace.configure_instance") as configure:
                with self.assertRaises(ValueError):
                    run(argparse.Namespace(output=output, seconds=10))
                configure.assert_not_called()

    def test_owned_lifecycle_and_setup_failure_preserve_global_state(self) -> None:
        """Stop before export and clean up only the new instance, including failure.

        Args: None.
        Returns: None.
        """
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                trace = root / "tracefs"
                (trace / "instances").mkdir(parents=True)
                (trace / "per_cpu/cpu0").mkdir(parents=True)
                (trace / "available_events").write_text("\n".join(EVENTS))
                (trace / "tracing_on").write_text("1\n")
                (trace / "current_tracer").write_text("nop\n")
                output = root / "recordings" / "new"

                def prepare(instance: Path, events: list[str], buffer_kb: int,
                            mmc_host: str | None = None) -> dict:
                    """Emulate files that tracefs creates automatically for an instance.

                    Args:
                        instance (Path): Owned temporary instance directory.
                        events (list[str]): Selected event names.
                        buffer_kb (int): Requested KiB per CPU.
                    Returns:
                        dict: Synthetic kernel configuration for lifecycle tests.
                    """
                    (instance / "events").mkdir()
                    (instance / "per_cpu/cpu0").mkdir(parents=True)
                    (instance / "per_cpu/cpu0/stats").write_text("overrun: 0\ncommit overrun: 0\ndropped events: 0\n")
                    (instance / "trace").write_text("# trace\n")
                    if fail:
                        raise ValueError("setup fixture failure")
                    return {"buffer_total_kb": buffer_kb, "event_formats": {}}

                def verify_export(source: io.BufferedReader, target: io.BufferedWriter) -> dict:
                    """Verify tracing is stopped before any trace output is copied.

                    Args:
                        source (io.BufferedReader): Synthetic trace input.
                        target (io.BufferedWriter): New output evidence stream.
                    Returns:
                        dict: Export counters from the real bounded copier.
                    """
                    instance = Path(source.name).parent
                    self.assertEqual((instance / "tracing_on").read_text(), "0\n")
                    return export_trace(source, target)

                with patch("profiling.kernel_io_trace.Path.cwd", return_value=root), patch("profiling.kernel_io_trace.TRACE_ROOT", trace), patch("profiling.kernel_io_trace.platform.system", return_value="Linux"), patch("profiling.kernel_io_trace.os.geteuid", return_value=0), patch("profiling.kernel_io_trace.configure_instance", side_effect=prepare), patch("profiling.kernel_io_trace.time.monotonic", side_effect=[10, 10.01, 10.02, 10.3, 10.31, 10.32] if not fail else [10, 10.01]), patch("profiling.kernel_io_trace.signal.signal"), patch("profiling.kernel_io_trace.os.chown"), patch("profiling.kernel_io_trace.Path.rmdir") as remove, patch("profiling.kernel_io_trace.export_trace", side_effect=verify_export):
                    result = run(argparse.Namespace(output=output, seconds=.1))
                self.assertEqual(result["status"], "error" if fail else "complete")
                self.assertFalse(result["buffer_loss_detected"])
                self.assertTrue(result["loss_accounting_complete"])
                remove.assert_called_once()
                self.assertEqual((trace / "tracing_on").read_text(), "1\n")
                self.assertEqual(json.loads((output / "summary.json").read_text())["status"], result["status"])


if __name__ == "__main__":
    unittest.main()
