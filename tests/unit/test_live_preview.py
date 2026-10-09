# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import BinaryIO

# Simulate binary/text streams entirely in memory.
import io

# Read or serialize metadata and browser/report payloads.
import json

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Express hardware-independent behavior as executable checks.
import unittest

# Reuse http.client helpers rather than duplicating their behavior here.
from http.client import HTTPConnection

# Keep failure handling alongside the operation so cleanup/status remains explicit.
try:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy
# Handle this failure without losing the error or skipping the enclosing cleanup.
except ImportError:
    # Set up numpy for this independent test scenario.
    numpy = None

# Choose the next branch using numpy is not None.
if numpy is not None:
    # Reuse app.live_preview helpers rather than duplicating their behavior here.
    from app.live_preview import (
        State,
        read_frame,
        rate,
        camera_command,
        make_server,
        make_handler,
    )


@unittest.skipIf(numpy is None, "NumPy required for preview tests")
class PreviewTests(unittest.TestCase):
    def test_pipe_reads_complete_partial_chunks(self) -> None:
        """Verify pipe reads complete partial chunks.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """

        class SmallReads(io.BytesIO):
            def read(self, size: int) -> bytes:
                """Force short binary reads to test frame assembly across pipe chunks.

                Args:
                    size (int): Expected raw-frame byte count; gray uses one byte per pixel.

                Returns:
                    bytes: The declared test-double result; only synthetic state is changed.
                """
                # Return the documented result to the caller without starting another operation.
                return super().read(min(size, 2))

        # Check the expected Equal relationship for this case.
        self.assertEqual(read_frame(SmallReads(b"abcdef"), 6), b"abcdef")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(read_frame(io.BytesIO(b""), 6))
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call read_frame for this step; its contract describes the result or side effect.
            read_frame(SmallReads(b"abc"), 6)

    def test_latest_frame_replaces_older_and_counts_skips(self) -> None:
        """Verify latest frame replaces older and counts skips.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise State with the controlled test inputs.
        state = State()
        # Exercise each fixture or edge case independently.
        for index in range(1, 5):
            # Publish completed work through the state object's synchronization boundary.
            state.publish_frame(bytes([index]), float(index))
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.latest, (4, 4.0, b"\x04"))
        # Publish completed work through the state object's synchronization boundary.
        state.publish_result(state.latest, 1, (2.0, -1.0, 7, 20.0), 3.5, 4.01)
        # Prepare or exercise state.snapshot with the controlled test inputs.
        result = state.snapshot(4.02)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["skipped"], 2)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["received"], 4)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["motion"], "reliable")
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["imu"]["status"], "off")
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["result_age_ms"], 20)

    def test_stale_error_and_unreliable_hide_arrows(self) -> None:
        """Verify stale error and unreliable hide arrows.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise State with the controlled test inputs.
        state = State()
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot()["status"], "starting")
        # Set up frame for this independent test scenario.
        frame = (2, 1.0, b"a")
        # Publish completed work through the state object's synchronization boundary.
        state.publish_result(frame, 1, None, 4.0, 1.1)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(1.2)["motion"], "unreliable")
        # Publish completed work through the state object's synchronization boundary.
        state.publish_result(frame, 1, (2.0, 3.0, 5, 12.0), 4.0, 1.1)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(4.0)["status"], "stale")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(state.snapshot(4.0)["dx"])
        # Call state.fail for this step; its contract describes the result or side effect.
        state.fail("camera disconnected")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(1.2)["status"], "error")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(state.snapshot(1.2)["dx"])

    def test_rates_and_command_modes(self) -> None:
        """Verify rates and command modes.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(rate([]))
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(rate([1, 1.1, 1.2]), 10)
        # Prepare or exercise camera_command with the controlled test inputs.
        command = camera_command("/dev/video9")
        # Check the expected Equal relationship for this case.
        self.assertEqual(command[command.index("-i") + 1], "/dev/video9")
        # Check the expected In relationship for this case.
        self.assertIn("1280x720", command)
        # Check the expected NotIn relationship for this case.
        self.assertNotIn("v4l2", camera_command(demo=True))

    def test_loopback_routes_and_no_file_serving(self) -> None:
        """Verify loopback routes and no file serving.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise State with the controlled test inputs.
        state = State()
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Prepare or exercise make_server with the controlled test inputs.
            server = make_server(state, 0)
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except PermissionError:
            # Call self.skipTest for this step; its contract describes the result or side
            # effect.
            self.skipTest(
                "Environment forbids binding a loopback socket; run this test on Pi"
            )
        # Prepare or exercise threading.Thread with the controlled test inputs.
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        # Start the worker so it can run independently of the caller's next step.
        thread.start()
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Check the expected Equal relationship for this case.
            self.assertEqual(server.server_address[0], "127.0.0.1")
            # Exercise each fixture or edge case independently.
            for path, expected in [
                ("/", 200),
                ("/api/frame", 200),
                ("/../../AGENTS.md", 404),
            ]:
                # Prepare or exercise HTTPConnection with the controlled test inputs.
                conn = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                # Call conn.request for this step; its contract describes the result or side
                # effect.
                conn.request("GET", path)
                # Prepare or exercise conn.getresponse with the controlled test inputs.
                response = conn.getresponse()
                # Prepare or exercise response.read with the controlled test inputs.
                body = response.read()
                # Check the expected Equal relationship for this case.
                self.assertEqual(response.status, expected)
                # Choose the next branch using path == '/api/frame'.
                if path == "/api/frame":
                    # Check the expected Equal relationship for this case.
                    self.assertEqual(json.loads(body)["status"], "starting")
                    # Check the expected Equal relationship for this case.
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                # Release the stream or server resource after use.
                conn.close()
            # Prepare or exercise HTTPConnection with the controlled test inputs.
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            # Call conn.request for this step; its contract describes the result or side effect.
            conn.request("GET", "/api/frame", headers={"Host": "unrelated.example"})
            # Prepare or exercise conn.getresponse with the controlled test inputs.
            response = conn.getresponse()
            # Call response.read for this step; its contract describes the result or side
            # effect.
            response.read()
            # Check the expected Equal relationship for this case.
            self.assertEqual(response.status, 403)
            # Release the stream or server resource after use.
            conn.close()
        finally:
            # Call server.shutdown for this step; its contract describes the result or side
            # effect.
            server.shutdown()
            # Release the stream or server resource after use.
            server.server_close()
            # Wait for this worker to finish, respecting the existing bounded timeout.
            thread.join(timeout=2)

    def test_http_responses_without_network(self) -> None:
        """Verify http responses without network.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """

        class Connection:
            def __init__(self, request: bytes) -> None:
                """Initialize the deterministic state used by this test double.

                Args:
                    request (bytes): Synthetic input used by this test double.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                # Prepare or exercise io.BytesIO with the controlled test inputs.
                self.input = io.BytesIO(request)
                # Prepare or exercise bytearray with the controlled test inputs.
                self.output = bytearray()

            def makefile(self, *args: object) -> BinaryIO:
                """Return the in-memory HTTP request stream for the handler.

                Args:
                    args (object): Parsed command-line options (or a compatible test fixture); see
                        main for fields.

                Returns:
                    BinaryIO: The declared test-double result; only synthetic state is changed.
                """
                # Return the documented result to the caller without starting another operation.
                return self.input

            def sendall(self, data: bytes) -> None:
                """Capture HTTP response bytes instead of sending them through a socket.

                Args:
                    data (bytes): Synthetic input used by this test double.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                # Retain this item/chunk for the current calculation or bounded history.
                self.output.extend(data)

        # Prepare or exercise State with the controlled test inputs.
        state = State()
        # Exercise each fixture or edge case independently.
        for path, host, status in [
            ("/", "localhost:8765", 200),
            ("/api/frame", "127.0.0.1:8765", 200),
            ("/../../AGENTS.md", "localhost:8765", 404),
            ("/api/frame", "external.example", 403),
        ]:
            # Prepare or exercise Connection with the controlled test inputs.
            connection = Connection(
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
            )
            # Call make_handler(state) for this step; its contract describes the result or side
            # effect.
            make_handler(state)(connection, ("127.0.0.1", 12345), None)
            # Prepare or exercise bytes(connection.output).split with the controlled test
            # inputs.
            header, body = bytes(connection.output).split(b"\r\n\r\n", 1)
            # Check the expected In relationship for this case.
            self.assertIn(f" {status} ".encode(), header.split(b"\r\n")[0])
            # Apply the freshness/status policy before exposing values to the user.
            if path == "/api/frame" and status == 200:
                # Check the expected Equal relationship for this case.
                self.assertEqual(json.loads(body)["status"], "starting")
                # Check the expected In relationship for this case.
                self.assertIn(b"Cache-Control: no-store", header)

    def test_startup_timeout_is_visible(self) -> None:
        """Verify startup timeout is visible.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise State with the controlled test inputs.
        state = State()
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(state.started + 11)["status"], "error")
