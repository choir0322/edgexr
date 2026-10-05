"""Loopback-only camera motion preview, accessed remotely using an SSH tunnel."""

import argparse
import base64
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import numpy as np

from recording.visual_motion import WIDTH, HEIGHT, image_shift
from imu.live_reader import LiveImu, poll_imu
from vision.live_detector import DetectionState, CpuDetector, detect_latest, SOURCE_WIDTH, SOURCE_HEIGHT


def read_frame(stream, size=WIDTH*HEIGHT):
    """Pipes can return partial reads; EOF midway through a frame is an error."""
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size-len(chunks))
        if not part:
            if chunks:
                raise ValueError('Camera pipe ended partway through a frame')
            return None
        chunks.extend(part)
    return bytes(chunks)


def rate(times):
    if len(times) < 2 or times[-1] <= times[0]:
        return None
    return (len(times)-1)/(times[-1]-times[0])


class State:
    def __init__(self, imu_enabled=False, detection_enabled=False):
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = None
        self.received = 0
        self.analyzed = 0
        self.skipped = 0
        self.capture_times = deque(maxlen=60)
        self.analysis_times = deque(maxlen=60)
        self.result = None
        self.error = None
        self.started = time.monotonic()
        self.imu = LiveImu(imu_enabled)
        self.detector = DetectionState(detection_enabled)
        self.detection_frame = None

    def publish_frame(self, pixels, timestamp, detection_pixels=None):
        with self.condition:
            self.received += 1
            self.latest = (self.received, timestamp, pixels)
            if detection_pixels is not None and self.detector.enabled:
                self.detection_frame = (self.received, timestamp, detection_pixels)
            self.capture_times.append(timestamp)
            self.condition.notify_all()

    def fail(self, message):
        with self.condition:
            self.error = message
            self.condition.notify_all()

    def publish_result(self, frame, previous_seq, shift, elapsed_ms, finished):
        seq, captured, pixels = frame
        result = dict(sequence=seq, captured=captured, analysis_ms=elapsed_ms,
                      pixels_b64=base64.b64encode(pixels).decode('ascii'),
                      dx=None, dy=None, patches=0, quality=None,
                      motion='warming up' if previous_seq == 0 else 'unreliable')
        if shift is not None:
            result.update(dx=shift[0], dy=shift[1], patches=shift[2], quality=shift[3],
                          motion='reliable')
        with self.condition:
            self.skipped += max(0, seq-previous_seq-1)
            self.analyzed += 1
            self.analysis_times.append(finished)
            self.result = result

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self.condition:
            result = dict(self.result) if self.result else {}
            age = now-result['captured'] if result else None
            status = 'error' if self.error else ('starting' if age is None else 'stale' if age > 2 else 'live')
            startup_timeout = age is None and now-self.started > 10
            if startup_timeout:
                status = 'error'
            result.update(status=status,error=self.error,width=WIDTH,height=HEIGHT,
                          received=self.received,analyzed=self.analyzed,skipped=self.skipped,
                          result_age_ms=age*1000 if age is not None else None,
                          capture_fps=rate([t for t in self.capture_times if now-t < 2]),
                          analysis_fps=rate([t for t in self.analysis_times if now-t < 2]))
            if startup_timeout and not self.error:
                result['error'] = 'No analyzed frame within 10 seconds. Check the camera path, permissions and other camera readers.'
            if status != 'live':
                result.update(motion='unavailable',dx=None,dy=None)
            result.pop('captured',None)
            result['imu'] = self.imu.snapshot(now)
            result['detector'] = self.detector.snapshot(now, status == 'live')
            return result


def analyze_latest(state):
    previous = None
    while not state.stop.is_set():
        with state.condition:
            state.condition.wait_for(lambda: state.stop.is_set() or state.error or
                (state.latest is not None and (previous is None or state.latest[0] != previous[0])), timeout=.5)
            if state.stop.is_set() or state.error:
                break
            frame = state.latest
        if frame is None or (previous is not None and frame[0] == previous[0]):
            continue
        try:
            begin = time.perf_counter()
            shift = None
            if previous is not None and frame[1]-previous[1] <= .5:
                first = np.frombuffer(previous[2],dtype=np.uint8).reshape(HEIGHT,WIDTH)
                second = np.frombuffer(frame[2],dtype=np.uint8).reshape(HEIGHT,WIDTH)
                shift = image_shift(first,second)
            elapsed = (time.perf_counter()-begin)*1000
            state.publish_result(frame,previous[0] if previous else 0,shift,elapsed,time.monotonic())
            previous = frame
        except Exception as error:
            state.fail(f'Analysis failed: {error}')
            break


def camera_command(device=None, demo=False, detection=False):
    command = ['ffmpeg','-hide_banner','-nostdin','-loglevel','warning']
    if demo:
        size = f'{SOURCE_WIDTH}x{SOURCE_HEIGHT}' if detection else f'{WIDTH}x{HEIGHT}'
        command += ['-re','-f','lavfi','-i',f'testsrc2=size={size}:rate=30']
    else:
        command += ['-f','v4l2','-input_format','mjpeg','-video_size','1280x720',
                    '-framerate','30','-i',device]
    width, height = (SOURCE_WIDTH, SOURCE_HEIGHT) if detection else (WIDTH, HEIGHT)
    return command+['-an','-vf',f'scale={width}:{height}','-pix_fmt','gray',
                    '-fps_mode','passthrough','-f','rawvideo','-']


def start_workers(state, command, cv=None):
    process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    diagnostics = deque(maxlen=8)

    def log_errors():
        for line in iter(process.stderr.readline,b''):
            diagnostics.append(line.decode(errors='replace').strip())

    def capture():
        try:
            while not state.stop.is_set():
                full_size = SOURCE_WIDTH*SOURCE_HEIGHT if state.detector.enabled else WIDTH*HEIGHT
                pixels = read_frame(process.stdout, full_size)
                if pixels is None:
                    if not state.stop.is_set():
                        state.fail('FFmpeg stopped. '+ ' | '.join(diagnostics))
                    return
                received = time.monotonic()
                if state.detector.enabled:
                    gray = np.frombuffer(pixels,dtype=np.uint8).reshape(SOURCE_HEIGHT,SOURCE_WIDTH)
                    small = cv.resize(gray,(WIDTH,HEIGHT),interpolation=cv.INTER_AREA).tobytes()
                    state.publish_frame(small,received,pixels)
                else:
                    state.publish_frame(pixels,received)
        except Exception as error:
            if not state.stop.is_set():
                state.fail(f'Capture failed: {error}')

    threads = [threading.Thread(target=target,daemon=True) for target in (log_errors,capture,lambda: analyze_latest(state))]
    for thread in threads:
        thread.start()
    return process, threads


def stop_workers(state, process, threads):
    state.stop.set()
    with state.condition:
        state.condition.notify_all()
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    for thread in threads:
        thread.join(timeout=3)
    process.stdout.close()
    process.stderr.close()


def make_handler(state):
    page = Path(__file__).with_name('preview.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Reject cross-site reads and DNS rebinding to non-loopback names.
            host = self.headers.get('Host','').split(':')[0]
            if host not in ('127.0.0.1','localhost') or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == '/':
                content, kind = page, 'text/html; charset=utf-8'
            elif path == '/api/frame':
                content = json.dumps(state.snapshot(),allow_nan=False).encode()
                kind = 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError,ConnectionResetError):
                pass

        def log_message(self,*args):
            pass

    return Handler


def make_server(state, port):
    server = ThreadingHTTPServer(('127.0.0.1',port),make_handler(state))
    server.daemon_threads = True
    server.timeout = .25
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--device',help='verified V4L2 camera path')
    source.add_argument('--demo',action='store_true',help='synthetic video; no camera access')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--imu',action='store_true',help='read SunFounder SH3001 gyro on a separate thread')
    parser.add_argument('--detect',action='store_true',help='MobileNet-SSD CPU boxes at a target 2 Hz')
    parser.add_argument('--prototxt',type=Path,default=Path('models/mobilenet-ssd/deploy.prototxt'))
    parser.add_argument('--weights',type=Path,default=Path('models/mobilenet-ssd/mobilenet_iter_73000.caffemodel'))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if not shutil.which('ffmpeg'):
        parser.error('existing FFmpeg installation required')
    cv = None
    if args.detect:
        try:
            import cv2 as cv
            cv.setNumThreads(2)
            cv.ocl.setUseOpenCL(False)
        except ImportError:
            parser.exit(1,'--detect requires OpenCV; see docs/DETECTION_BASELINE.md\n')
    state = State(imu_enabled=args.imu, detection_enabled=args.detect)
    process = None
    server = None
    try:
        server = make_server(state,args.port)
        process,threads = start_workers(state,camera_command(args.device,args.demo,args.detect),cv)
        if args.detect:
            factory = lambda: CpuDetector(cv,args.prototxt,args.weights)
            worker = threading.Thread(target=detect_latest,args=(state,factory),daemon=True)
            worker.start()
            threads.append(worker)
        if args.imu:
            try:
                from sunfounder_imu import IMU
                sensor = IMU().accel_gyro
                if sensor is None:
                    raise ValueError('No accelerometer/gyroscope found')
                imu_thread = threading.Thread(target=poll_imu,args=(state.imu,sensor,state.stop),daemon=True)
                imu_thread.start()
                threads.append(imu_thread)
            except Exception as error:
                state.imu.fail(f'IMU setup failed: {error}')
        print(f'Preview: http://127.0.0.1:{args.port} (use SSH forwarding from your Mac).',flush=True)
        print('Camera: synthetic demo' if args.demo else f'Camera: {args.device}, requested 1280x720 MJPEG at 30 fps',flush=True)
        print('Analysis: 320x180 grayscale. No footage saved. Ctrl+C stops.',flush=True)
        if args.detect:
            print('Detection: 720p source -> 300x300 model, CPU 2 threads, target 2 Hz. Boxes may lag; age shown.',flush=True)
        if args.imu:
            print('IMU: first second must be still; using per-run raw gyro offset. IMU errors appear in browser.',flush=True)
        while not state.stop.is_set():
            server.handle_request()
    except KeyboardInterrupt:
        print('\nStopping preview.')
    except OSError as error:
        parser.exit(1,f'Preview failed: {error}\n')
    finally:
        if process is not None:
            stop_workers(state,process,threads)
        if server is not None:
            server.server_close()


if __name__ == '__main__':
    main()
