import io
import json
import threading
import unittest
from http.client import HTTPConnection

try:
    import numpy
except ImportError:
    numpy = None

if numpy is not None:
    from app.live_preview import State, read_frame, rate, camera_command, make_server, make_handler


@unittest.skipIf(numpy is None,'NumPy required for preview tests')
class PreviewTests(unittest.TestCase):
    def test_pipe_reads_complete_partial_chunks(self):
        class SmallReads(io.BytesIO):
            def read(self,size):
                return super().read(min(size,2))
        self.assertEqual(read_frame(SmallReads(b'abcdef'),6),b'abcdef')
        self.assertIsNone(read_frame(io.BytesIO(b''),6))
        with self.assertRaises(ValueError):
            read_frame(SmallReads(b'abc'),6)

    def test_latest_frame_replaces_older_and_counts_skips(self):
        state=State()
        for index in range(1,5):
            state.publish_frame(bytes([index]),float(index))
        self.assertEqual(state.latest,(4,4.0,b'\x04'))
        state.publish_result(state.latest,1,(2.,-1.,7,20.),3.5,4.01)
        result=state.snapshot(4.02)
        self.assertEqual(result['skipped'],2)
        self.assertEqual(result['received'],4)
        self.assertEqual(result['motion'],'reliable')
        self.assertAlmostEqual(result['result_age_ms'],20)

    def test_stale_error_and_unreliable_hide_arrows(self):
        state=State()
        self.assertEqual(state.snapshot()['status'],'starting')
        frame=(2,1.,b'a')
        state.publish_result(frame,1,None,4.,1.1)
        self.assertEqual(state.snapshot(1.2)['motion'],'unreliable')
        state.publish_result(frame,1,(2.,3.,5,12.),4.,1.1)
        self.assertEqual(state.snapshot(4.)['status'],'stale')
        self.assertIsNone(state.snapshot(4.)['dx'])
        state.fail('camera disconnected')
        self.assertEqual(state.snapshot(1.2)['status'],'error')
        self.assertIsNone(state.snapshot(1.2)['dx'])

    def test_rates_and_command_modes(self):
        self.assertIsNone(rate([]))
        self.assertAlmostEqual(rate([1,1.1,1.2]),10)
        command=camera_command('/dev/video9')
        self.assertEqual(command[command.index('-i')+1],'/dev/video9')
        self.assertIn('1280x720',command)
        self.assertNotIn('v4l2',camera_command(demo=True))

    def test_loopback_routes_and_no_file_serving(self):
        state=State()
        try:
            server=make_server(state,0)
        except PermissionError:
            self.skipTest('Environment forbids binding a loopback socket; run this test on Pi')
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            self.assertEqual(server.server_address[0],'127.0.0.1')
            for path,expected in [('/',200),('/api/frame',200),('/../../AGENTS.md',404)]:
                conn=HTTPConnection('127.0.0.1',server.server_port,timeout=2)
                conn.request('GET',path)
                response=conn.getresponse();body=response.read()
                self.assertEqual(response.status,expected)
                if path=='/api/frame':
                    self.assertEqual(json.loads(body)['status'],'starting')
                    self.assertEqual(response.getheader('Cache-Control'),'no-store')
                conn.close()
            conn=HTTPConnection('127.0.0.1',server.server_port,timeout=2)
            conn.request('GET','/api/frame',headers={'Host':'unrelated.example'})
            response=conn.getresponse();response.read()
            self.assertEqual(response.status,403)
            conn.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_http_responses_without_network(self):
        class Connection:
            def __init__(self,request):
                self.input=io.BytesIO(request)
                self.output=bytearray()
            def makefile(self,*args):
                return self.input
            def sendall(self,data):
                self.output.extend(data)
        state=State()
        for path,host,status in [('/','localhost:8765',200),('/api/frame','127.0.0.1:8765',200),
                                 ('/../../AGENTS.md','localhost:8765',404),('/api/frame','external.example',403)]:
            connection=Connection(f'GET {path} HTTP/1.1\r\nHost: {host}\r\n\r\n'.encode())
            make_handler(state)(connection,('127.0.0.1',12345),None)
            header,body=bytes(connection.output).split(b'\r\n\r\n',1)
            self.assertIn(f' {status} '.encode(),header.split(b'\r\n')[0])
            if path=='/api/frame' and status==200:
                self.assertEqual(json.loads(body)['status'],'starting')
                self.assertIn(b'Cache-Control: no-store',header)

    def test_startup_timeout_is_visible(self):
        state=State()
        self.assertEqual(state.snapshot(state.started+11)['status'],'error')
