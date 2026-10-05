import threading
import unittest

from imu.live_reader import LiveImu, stationary_offset, poll_imu


class LiveImuTests(unittest.TestCase):
    def test_independent_still_window_estimates_offset_and_corrects_new_sample(self):
        imu=LiveImu(enabled=True)
        for i in range(11):
            imu.publish(i*.1,(-4.0+.02*(i%2),15.0,-3.0))
        result=imu.snapshot(1.01)
        self.assertEqual(result['status'],'ready')
        self.assertAlmostEqual(result['offset_dps'][1],15.)
        self.assertAlmostEqual(result['gyro_dps'][1],0.)
        imu.publish(1.1,(-4.,25.,-3.))
        result=imu.snapshot(1.11)
        self.assertEqual(result['gyro_dps'][1],10.)
        self.assertEqual(result['samples'],12)
        self.assertGreater(result['rate_hz'],9.)

    def test_motion_during_calibration_is_reported_not_applied(self):
        imu=LiveImu(enabled=True)
        for i in range(11):
            imu.publish(i*.1,(0.,0. if i<5 else 12.,0.))
        result=imu.snapshot(1.02)
        self.assertEqual(result['status'],'error')
        self.assertIsNone(result['gyro_dps'])
        self.assertIn('restart',result['error'])
        imu.publish(1.1,(0.,0.,0.))
        self.assertEqual(imu.snapshot(1.12)['status'],'error')

    def test_stale_and_read_error_do_not_return_old_corrected_rate(self):
        imu=LiveImu(enabled=True)
        self.assertEqual(imu.snapshot(imu.started+3)['status'],'stale')
        for i in range(11):
            imu.publish(i*.1,(0.,0.,0.))
        self.assertEqual(imu.snapshot(1.31)['status'],'stale')
        self.assertIsNone(imu.snapshot(1.31)['gyro_dps'])
        imu.fail('i2c failed')
        self.assertEqual(imu.snapshot(1.11)['status'],'error')
        self.assertIsNone(imu.snapshot(1.11)['gyro_dps'])

    def test_not_enough_samples_nonfinite_and_out_of_order_rejected(self):
        with self.assertRaises(ValueError):
            stationary_offset([(0.,(0.,0.,0.))])
        imu=LiveImu(enabled=True)
        for gyro in [(0.,float('nan'),0.),(1.,2.),(1.,float('inf'),2.)]:
            with self.assertRaises(ValueError):
                imu.publish(0.,gyro)
        imu.publish(1.,(1.,2.,3.))
        with self.assertRaises(ValueError):
            imu.publish(1.,(1.,2.,3.))

    def test_fake_sensor_is_polled_and_failure_is_isolated(self):
        class Sensor:
            def __init__(self): self.calls=0
            def read_raw(self):
                self.calls+=1
                if self.calls>12:raise OSError('disconnected')
                return (0.,0.,1.),(-4.,15.,-3.),25.
        class Clock:
            def __init__(self): self.n=0
            def __call__(self):
                value=self.n*.05
                self.n+=1
                return value
        imu=LiveImu(enabled=True)
        poll_imu(imu,Sensor(),threading.Event(),interval=.00001,clock=Clock())
        self.assertEqual(imu.samples,12)
        self.assertIn('disconnected',imu.snapshot(1.2)['error'])
