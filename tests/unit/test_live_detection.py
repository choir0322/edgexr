import unittest

try:
    import numpy as np
except ImportError:
    np = None

from vision.live_detector import DetectionState, detect_latest
if np is not None:
    from app.live_preview import State, camera_command


class DetectionStateTests(unittest.TestCase):
    def test_age_stale_error_camera_failure_and_empty_detection(self):
        state = DetectionState(True)
        self.assertEqual(state.snapshot(state.started)['status'], 'starting')
        self.assertEqual(state.snapshot(state.started+11)['status'], 'stale')
        state.publish((1,10,b''), [{'label':'chair'}], 200, 10.2)
        self.assertAlmostEqual(state.snapshot(10.3)['age_ms'], 300)
        self.assertEqual(state.snapshot(10.3)['status'], 'ready')
        self.assertEqual(state.snapshot(12)['boxes'], [])
        self.assertEqual(state.snapshot(10.3,False)['boxes'], [])
        state.publish((2,10.5,b''), [], 201, 10.7)
        self.assertEqual(state.snapshot(10.8)['status'], 'ready')
        self.assertAlmostEqual(state.snapshot(10.8)['rate_hz'], 2)
        state.fail('bad model')
        self.assertEqual(state.snapshot(10.8)['status'], 'error')
        self.assertEqual(state.snapshot(10.8)['boxes'], [])
        self.assertEqual(DetectionState().snapshot(1)['status'], 'off')


@unittest.skipIf(np is None, 'NumPy required for preview')
class LiveDetectionTests(unittest.TestCase):
    def test_full_frame_is_separate_from_motion_and_latest_replaces_older(self):
        state=State(detection_enabled=True)
        state.publish_frame(b'small1',1,b'full1')
        state.publish_frame(b'small2',2,b'full2')
        self.assertEqual(state.latest,(2,2,b'small2'))
        self.assertEqual(state.detection_frame,(2,2,b'full2'))
        state.publish_result(state.latest,1,None,1,2.01)
        state.detector.publish(state.detection_frame,[],200,2.2)
        self.assertEqual(state.snapshot(2.3)['detector']['status'],'ready')
        state.fail('camera gone')
        self.assertEqual(state.snapshot(2.3)['detector']['status'],'unavailable')
        self.assertIn('scale=1280:720',camera_command('/dev/video0',detection=True))
        self.assertIn('scale=320:180',camera_command('/dev/video0'))

    def test_worker_rate_limits_and_skips_backlog_even_when_slow(self):
        for duration in (.2,.8):
            with self.subTest(duration=duration):
                clock=[100.]
                class Stop:
                    stopped=False
                    def is_set(self): return self.stopped
                    def set(self): self.stopped=True
                    def wait(self,seconds):
                        clock[0]+=seconds
                        return self.stopped
                state=State(detection_enabled=True)
                state.stop=Stop()
                state.publish_frame(b'',clock[0],b'one')
                calls=[]
                def detector(pixels):
                    calls.append((clock[0],pixels))
                    clock[0]+=duration
                    if len(calls)==1:
                        state.publish_frame(b'',clock[0],b'two')
                        state.publish_frame(b'',clock[0],b'three')
                    else:
                        state.stop.set()
                    return []
                detect_latest(state,lambda:detector,lambda:clock[0])
                self.assertEqual([c[1] for c in calls],[b'one',b'three'])
                self.assertAlmostEqual(calls[1][0]-calls[0][0],max(.5,duration))
                self.assertIsNone(state.error)

    def test_detector_failure_does_not_fail_camera(self):
        state=State(detection_enabled=True)
        def broken(): raise ValueError('invalid model')
        detect_latest(state,broken)
        self.assertIsNone(state.error)
        self.assertIn('invalid model',state.detector.snapshot(1)['error'])
        self.assertFalse(state.stop.is_set())
