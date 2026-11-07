"""Bounded observer output checks without a Pi, camera or mounts."""

from pathlib import Path
import tempfile
import unittest

from profiling.sample_sink import SampleSink


class SampleSinkTests(unittest.TestCase):
    def test_ram_bound_counts_utf8_and_never_spills(self) -> None:
        """Reject a whole row without changing previously accepted data.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.jsonl"
            sink = SampleSink(path, "ram", 4)
            sink.write("é\n")
            self.assertFalse(path.exists())
            with self.assertRaises(BufferError):
                sink.write("aa\n")
            self.assertEqual(sink.payload_bytes, 3)
            self.assertEqual(sink.rows, 1)
            self.assertTrue(sink.overflow)
            sink.close()
            result = sink.export()
            self.assertEqual(result["status"], "complete")
            self.assertEqual(path.read_bytes(), "é\n".encode())

    def test_ordered_export_and_file_match(self) -> None:
        """Both destinations preserve identical ordered payloads.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for mode in ("ram", "file"):
                sink = SampleSink(root / mode, mode, 100)
                for row in ('{"n":1}\n', '{"n":2}\n'):
                    sink.write(row)
                with self.assertRaises(ValueError):
                    sink.export()
                sink.close()
                sink.export()
                with self.assertRaises(ValueError):
                    sink.write("late")
            self.assertEqual((root / "ram").read_bytes(), (root / "file").read_bytes())

    def test_export_failure_retains_memory_and_existing_evidence(self) -> None:
        """A conflicting output produces explicit failure, not overwrite.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.jsonl"
            sink = SampleSink(path, "ram", 100)
            sink.write("new\n")
            sink.close()
            path.write_text("original")
            self.assertEqual(sink.export()["status"], "failed")
            self.assertEqual(path.read_text(), "original")
            self.assertEqual(sink.chunks, [b"new\n"])
            with self.assertRaises(FileExistsError):
                SampleSink(path, "file", 100)

    def test_partial_output_is_not_overwritten(self) -> None:
        """Preserve a previous partial export and report a retry failure.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.jsonl"
            sink = SampleSink(path, "ram", 100)
            sink.write("new")
            sink.close()
            partial = path.with_suffix(".jsonl.partial")
            partial.write_text("old partial")
            self.assertEqual(sink.export()["status"], "failed")
            self.assertEqual(partial.read_text(), "old partial")
            self.assertFalse(path.exists())
