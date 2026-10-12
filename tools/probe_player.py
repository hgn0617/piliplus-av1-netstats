#!/usr/bin/env python3
"""Inspect libavcodec capabilities and optionally decode a file with libmpv."""
import argparse
import ctypes as c
import json
from pathlib import Path
import time


class HWConfig(c.Structure):
    _fields_ = [('pix_fmt', c.c_int), ('methods', c.c_int), ('device_type', c.c_int)]


class Event(c.Structure):
    _fields_ = [('event_id', c.c_int), ('error', c.c_int),
                ('reply_userdata', c.c_uint64), ('data', c.c_void_p)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('app', type=Path)
    ap.add_argument('--file', type=Path)
    ap.add_argument('--hwdec', default='videotoolbox-copy')
    ap.add_argument('--seconds', type=float, default=4)
    args = ap.parse_args()
    binary = args.app / 'Contents/Frameworks/Mpv.framework/Versions/A/Mpv'
    mpv = c.CDLL(str(binary))
    mpv.mpv_client_api_version.restype = c.c_ulong
    runtime = binary.parent / 'AV1Runtime'
    av_path = runtime / 'libavcodec.63.dylib' if runtime.exists() else args.app / 'Contents/Frameworks/Avcodec.framework/Versions/A/Avcodec'
    av = c.CDLL(str(av_path))
    av.avcodec_version.restype = c.c_uint
    av.avcodec_find_decoder_by_name.argtypes = [c.c_char_p]
    av.avcodec_find_decoder_by_name.restype = c.c_void_p
    av.avcodec_get_hw_config.argtypes = [c.c_void_p, c.c_int]
    av.avcodec_get_hw_config.restype = c.POINTER(HWConfig)
    util_path = runtime / 'libavutil.61.dylib' if runtime.exists() else args.app / 'Contents/Frameworks/Avutil.framework/Versions/A/Avutil'
    util = c.CDLL(str(util_path))
    util.av_hwdevice_get_type_name.argtypes = [c.c_int]
    util.av_hwdevice_get_type_name.restype = c.c_char_p
    version = av.avcodec_version()
    result = {'app': str(args.app), 'mpv_client_api_version': mpv.mpv_client_api_version(),
              'avcodec_version': f'{version >> 16}.{version >> 8 & 255}.{version & 255}', 'decoders': {}}
    for name in ('av1', 'libdav1d', 'hevc', 'h264'):
        codec = av.avcodec_find_decoder_by_name(name.encode())
        configs = []
        for i in range(50):
            hw = av.avcodec_get_hw_config(codec, i) if codec else None
            if not hw:
                break
            hw = hw.contents
            device = util.av_hwdevice_get_type_name(hw.device_type)
            configs.append({'device': device.decode() if device else None, 'methods': hw.methods})
        result['decoders'][name] = configs
    if args.file:
        mpv.mpv_create.restype = c.c_void_p
        mpv.mpv_set_option_string.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
        mpv.mpv_initialize.argtypes = [c.c_void_p]
        mpv.mpv_command.argtypes = [c.c_void_p, c.POINTER(c.c_char_p)]
        mpv.mpv_get_property_string.argtypes = [c.c_void_p, c.c_char_p]
        mpv.mpv_get_property_string.restype = c.c_void_p
        mpv.mpv_wait_event.argtypes = [c.c_void_p, c.c_double]
        mpv.mpv_wait_event.restype = c.POINTER(Event)
        mpv.mpv_free.argtypes = [c.c_void_p]
        mpv.mpv_terminate_destroy.argtypes = [c.c_void_p]
        handle = mpv.mpv_create()
        def prop(key):
            value = mpv.mpv_get_property_string(handle, key.encode())
            if not value:
                return None
            text = c.string_at(value).decode()
            mpv.mpv_free(value)
            return text
        for k, v in {'vo': 'null', 'ao': 'null', 'hwdec': args.hwdec,
                     'hwdec-codecs': 'all', 'loop-file': 'inf', 'terminal': 'yes',
                     'msg-level': 'all=warn,vd=info', 'config': 'no'}.items():
            code = mpv.mpv_set_option_string(handle, k.encode(), v.encode())
            if code < 0:
                raise RuntimeError(f'Option {k} failed: {code}')
        if mpv.mpv_initialize(handle) < 0:
            raise RuntimeError('mpv_initialize failed')
        command = (c.c_char_p * 3)(b'loadfile', str(args.file).encode(), None)
        if mpv.mpv_command(handle, command) < 0:
            raise RuntimeError('loadfile failed')
        deadline = time.monotonic() + args.seconds
        snapshots = []
        while time.monotonic() < deadline:
            mpv.mpv_wait_event(handle, .1)
            info = {k: prop(k) for k in ('video-codec', 'video-params', 'hwdec-current',
                                        'video-dec-params', 'decoder-frame-drop-count', 'time-pos')}
            if info['video-codec'] and (not snapshots or info != snapshots[-1]):
                snapshots.append(info)
        result['playback'] = snapshots[-5:]
        mpv.mpv_terminate_destroy(handle)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
