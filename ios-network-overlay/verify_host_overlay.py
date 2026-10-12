import ctypes as c
import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
sample = (BASE.parent / 'verification/av1-sample.ivf').read_bytes()
header = bytearray(sample[:32])
frames = []
offset = 32
while offset < len(sample):
    size = struct.unpack_from('<I', sample, offset)[0]
    frames.append(sample[offset+12:offset+12+size])
    offset += 12 + size
struct.pack_into('<I', header, 24, len(frames) * 30)
data = bytes(header) + b''.join(struct.pack('<IQ', len(f), i) + f
    for i, f in enumerate(frames * 30))


class Server(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        start = 0
        if self.headers.get('Range'):
            start = int(self.headers['Range'].split('=')[1].split('-')[0])
        self.send_response(206 if start else 200)
        self.send_header('Content-Length', str(len(data)-start))
        self.send_header('Content-Type', 'video/x-ivf')
        self.send_header('Accept-Ranges', 'bytes')
        if start:
            self.send_header('Content-Range', f'bytes {start}-{len(data)-1}/{len(data)}')
        self.end_headers()
        try:
            for pos in range(start, len(data), 4096):
                self.wfile.write(data[pos:pos+4096]); self.wfile.flush()
                time.sleep(.085)
        except (BrokenPipeError, ConnectionResetError):
            pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Server)
threading.Thread(target=server.serve_forever, daemon=True).start()
mpv = c.CDLL(str(BASE / 'host-test/Mpv.framework/Mpv'))
mpv.piliplus_network_test_preferences.argtypes = [c.c_int,c.c_double,c.c_char_p]
mpv.piliplus_network_test_preferences(1,1.0,b'top-right')
mpv.mpv_create.restype = c.c_void_p
mpv.mpv_initialize.argtypes = [c.c_void_p]
mpv.mpv_set_option_string.argtypes = [c.c_void_p,c.c_char_p,c.c_char_p]
mpv.mpv_get_property_string.argtypes = [c.c_void_p,c.c_char_p]
mpv.mpv_get_property_string.restype = c.c_void_p
mpv.mpv_free.argtypes = [c.c_void_p]
mpv.mpv_command.argtypes = [c.c_void_p,c.POINTER(c.c_char_p)]
mpv.mpv_terminate_destroy.argtypes = [c.c_void_p]


class Param(c.Structure):
    _fields_ = [('type', c.c_int), ('data', c.c_void_p)]


mpv.mpv_render_context_create.argtypes = [c.POINTER(c.c_void_p), c.c_void_p,c.POINTER(Param)]
mpv.mpv_render_context_render.argtypes = [c.c_void_p,c.POINTER(Param)]
mpv.mpv_render_context_free.argtypes = [c.c_void_p]
h = mpv.mpv_create()
for k,v in {'vo':'libmpv','ao':'null','hwdec':'videotoolbox-copy','hwdec-codecs':'all',
            'terminal':'yes','msg-level':'all=warn','idle':'yes','cache':'yes',
            'cache-secs':'16','osd-level':'0'}.items():
    assert mpv.mpv_set_option_string(h,k.encode(),v.encode()) >= 0
assert mpv.mpv_initialize(h) >= 0
api = c.create_string_buffer(b'sw')
init = (Param*2)(Param(1,c.cast(api,c.c_void_p)),Param(0,None))
ctx = c.c_void_p()
assert mpv.mpv_render_context_create(c.byref(ctx),h,init) >= 0
url = f'http://127.0.0.1:{server.server_port}/sample.ivf'
assert mpv.mpv_command(h,(c.c_char_p*3)(b'loadfile',url.encode(),None)) >= 0
width,height=1280,720
size=(c.c_int*2)(width,height)
fmt=c.create_string_buffer(b'rgb0');stride=c.c_size_t(width*4);block=c.c_int(0)
storage=c.create_string_buffer(width*height*4+64)
aligned=(c.addressof(storage)+63)&~63
params=(Param*6)(Param(17,c.cast(size,c.c_void_p)),Param(18,c.cast(fmt,c.c_void_p)),
    Param(19,c.cast(c.byref(stride),c.c_void_p)),Param(20,aligned),
    Param(12,c.cast(c.byref(block),c.c_void_p)),Param(0,None))


def prop(key):
    value=mpv.mpv_get_property_string(h,key.encode())
    if not value:return None
    text=c.string_at(value).decode();mpv.mpv_free(value)
    return text


snapshots=[]
deadline=time.monotonic()+5
while time.monotonic()<deadline:
    assert mpv.mpv_render_context_render(ctx,params)>=0
    if prop('user-data/piliplus-network/visible')=='true':
        snapshots.append({k:prop(k) for k in ['hwdec-current','time-pos',
            'user-data/piliplus-network/bytes_per_second',
            'user-data/piliplus-network/buffered_seconds']})
    time.sleep(.04)
Image.frombytes('RGBX',(width,height),c.string_at(aligned,width*height*4)).convert('RGB').save(BASE/'overlay-preview.png')
assert snapshots and any(float(x['user-data/piliplus-network/bytes_per_second'] or 0)>1000 for x in snapshots)
assert any(x['hwdec-current']=='videotoolbox-copy' for x in snapshots)
assert snapshots[-1]['time-pos'] is not None
def wait_status(key, expected):
    until=time.monotonic()+2
    while time.monotonic()<until:
        mpv.mpv_render_context_render(ctx,params)
        value=json.loads(prop('user-data/piliplus-network') or '{}').get(key)
        if value==expected:return
        time.sleep(.03)
    raise AssertionError((key,expected,prop('user-data/piliplus-network')))

for enabled in [0,1]:
    mpv.piliplus_network_test_preferences(enabled,1.0,b'top-right')
    wait_status('enabled',bool(enabled))
for scale in [.8,1.0,1.25,1.5]:
    mpv.piliplus_network_test_preferences(1,scale,b'top-right')
    wait_status('scale',scale)
for corner in ['top-left','bottom-left','bottom-right','top-right']:
    mpv.piliplus_network_test_preferences(1,1.0,corner.encode())
    wait_status('corner',corner)
    assert mpv.mpv_render_context_render(ctx,params)>=0

assert mpv.mpv_set_option_string(h,b'vid',b'no')>=0
wait_status('visible',False)
assert mpv.mpv_command(h,(c.c_char_p*3)(b'loadfile',str(BASE.parent/'verification/av1-sample.ivf').encode(),None))>=0
assert mpv.mpv_set_option_string(h,b'vid',b'auto')>=0
wait_status('visible',False)
mpv.mpv_render_context_free(ctx);mpv.mpv_terminate_destroy(h);server.shutdown()
result={'controlled_http_read_rate_positive':True,'video_progresses':True,
        'av1_hardware_decode_preserved':True,'toggle_messages_pass':True,
        'font_size_messages_pass':True,'four_corner_messages_pass':True,'audio_only_and_local_video_overlay_hidden':True,'test_scope':'Same native iOS bridge source compiled on macOS; not an iPhone runtime test',
        'preview_size':[width,height],'last_snapshot':snapshots[-1]}
(BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
