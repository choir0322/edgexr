import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from recording.visual_motion import patch_shift, image_shift, validate_video_times, gyro_at


@unittest.skipIf(np is None, 'Optional NumPy required for offline image-analysis tests')
class VisualMotionTests(unittest.TestCase):
    def test_known_shifts_have_correct_sign(self):
        image = np.random.default_rng(4).normal(120,30,(56,80))
        for dx,dy in [(0,0),(3,-2),(-4,2)]:
            result = patch_shift(image,np.roll(image,(dy,dx),axis=(0,1)))
            self.assertIsNotNone(result)
            self.assertAlmostEqual(result[0],dx,delta=.15)
            self.assertAlmostEqual(result[1],dy,delta=.15)

    def test_flat_and_unrelated_patches_rejected(self):
        self.assertIsNone(patch_shift(np.zeros((56,80)),np.zeros((56,80))))
        rng = np.random.default_rng(32)
        self.assertIsNone(patch_shift(rng.normal(120,30,(56,80)),rng.normal(120,30,(56,80))))

    def test_patch_consensus_handles_local_outlier(self):
        rng = np.random.default_rng(9)
        a = rng.normal(120,30,(180,320))
        b = np.roll(a,(1,3),axis=(0,1))
        b[:61,:85] = rng.normal(120,30,b[:61,:85].shape)
        result = image_shift(a,b)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0],3,delta=.2)
        self.assertAlmostEqual(result[1],1,delta=.2)

    def test_video_log_pairing_checks_count_and_pts(self):
        rows = [dict(frame_index=i,camera_pts_s=t) for i,t in enumerate([0,.14802,.180026])]
        self.assertLess(validate_video_times([0,.148,.180],rows),.001)
        for times in ([0,.148],[0,.148,.28],[0,.148,.148]):
            with self.assertRaises(ValueError):
                validate_video_times(times,rows)
        rows[-1]['frame_index']=9
        with self.assertRaises(ValueError):
            validate_video_times([0,.148,.180],rows)

    def test_interpolation_never_extrapolates_or_crosses_large_gap(self):
        times = np.array([0,.05,.10,.4])
        values = np.array([[0,0,0],[2,4,6],[4,8,12],[6,12,18]])
        np.testing.assert_allclose(gyro_at(.025,times,values),[1,2,3])
        for t in [-.1,.2,.5]:
            self.assertIsNone(gyro_at(t,times,values))
