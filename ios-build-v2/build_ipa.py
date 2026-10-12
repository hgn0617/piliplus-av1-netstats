#!/usr/bin/env python3
"""Replace ONLY the original iOS Avcodec framework executable.

Source IPA, mpv, Avformat, Avutil, TLS, audio and Flutter libraries are preserved.
Final device signing/provisioning is performed by Sideloadly.
"""
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / 'ios-check/PiliPlus_ios_2.1.6+5472.ipa'
STAGE = BASE / 'staging'
OUTPUT = BASE / 'PiliPlus_iOS_2.1.6+5472_AV1-v2.ipa'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exports(path):
    result = set()
    for line in run('xcrun', 'dyld_info', '-exports', str(path)).splitlines():
        match = re.match(r'\s+(?:0x[0-9A-Fa-f]+|\[re-export\])\s+(_\S+)', line)
        if match:
            result.add(match[1])
    return result


def executable_text_hash(path):
    sections = run('otool', '-l', str(path))
    match = re.search(r'sectname __text\s+segname __TEXT\s+addr \S+\s+size (0x[0-9a-fA-F]+)\s+offset (\d+)', sections)
    assert match, 'Missing executable text section'
    size, offset = int(match[1], 16), int(match[2])
    return hashlib.sha256(path.read_bytes()[offset:offset+size]).hexdigest()


def main():
    assert sha(SOURCE) == '6cccd84c5459fbefeef2683659e7dbe3d65a76243862525d24238303d9a341ee'
    assert not STAGE.exists(), 'Move existing staging before rebuilding'
    STAGE.mkdir()
    with zipfile.ZipFile(SOURCE) as z:
        assert z.testzip() is None
        for entry in z.infolist():
            rel = Path(entry.filename)
            assert not rel.is_absolute() and '..' not in rel.parts
            mode = entry.external_attr >> 16
            assert not stat.S_ISLNK(mode)
            dest = STAGE / rel
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(entry))
                os.chmod(dest, stat.S_IMODE(mode) or 0o644)

    app = STAGE / 'Payload/Runner.app'
    framework = app / 'Frameworks/Avcodec.framework'
    binary = framework / 'Avcodec'
    preserved = {str(p.relative_to(app)): sha(p) for p in app.rglob('*')
                 if p.is_file() and not p.is_relative_to(framework)
                 and p not in [app / 'Info.plist', app / 'Runner']}
    runner_text = executable_text_hash(app / 'Runner')
    original_exports = exports(binary)
    replacement = BASE / 'Avcodec-new'
    assert exports(replacement) == original_exports
    symbols = run('nm', str(replacement))
    assert '_ff_av1_videotoolbox_hwaccel' in symbols
    assert '_videotoolbox_av1_end_frame' in symbols
    for name in ['aac', 'h264', 'hevc', 'libdav1d']:
        assert '_ff_' + name + '_decoder' in symbols
    assert 'platform 2' in run('otool', '-l', str(replacement))
    deps = run('otool', '-L', str(replacement))
    assert 'compatibility version 61.0.0, current version 61.3.100' in deps
    assert '/Users/' not in '\n'.join(deps.splitlines()[1:])
    shutil.copy2(replacement, binary)
    os.chmod(binary, 0o755)
    run('strip', '-x', str(binary))
    assert exports(binary) == original_exports

    info = plistlib.loads((framework / 'Info.plist').read_bytes())
    info['MinimumOSVersion'] = '15.0'
    (framework / 'Info.plist').write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    info['CFBundleDisplayName'] = 'PiliPlus AV1 v2'
    (app / 'Info.plist').write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    run('codesign', '--force', '--sign', '-', '--timestamp=none', str(framework))
    # Every other original embedded framework already has a valid signature.
    # Do not re-sign or alter them: preserve their exact bytes.
    run('codesign', '--force', '--sign', '-', '--timestamp=none', str(app))
    run('codesign', '--verify', '--deep', '--strict', str(app))
    for rel, digest in preserved.items():
        assert sha(app / rel) == digest, 'Unexpected modification: ' + rel
    assert executable_text_hash(app / 'Runner') == runner_text

    with zipfile.ZipFile(OUTPUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted((STAGE / 'Payload').rglob('*')):
            z.write(p, str(p.relative_to(STAGE)))
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        assert z.read('Payload/Runner.app/Frameworks/Avcodec.framework/Avcodec') == binary.read_bytes()
        assert z.read('Payload/Runner.app/Frameworks/Mpv.framework/Mpv') == (app / 'Frameworks/Mpv.framework/Mpv').read_bytes()

    original_app = BASE.parent / 'ios-check/unpacked/Payload/Runner.app'
    manifest = {
        'output': OUTPUT.name, 'sha256': sha(OUTPUT), 'size_bytes': OUTPUT.stat().st_size,
        'base_release': 'https://github.com/bggRGjQaUbCoE/PiliPlus/releases/tag/2.1.6.2',
        'base_sha256': sha(SOURCE),
        'patch_commit': 'https://github.com/FFmpeg/FFmpeg/commit/f9c5c5358cfef3847674c6f3b3ded9611ebc5647',
        'ffmpeg_source': 'https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.xz',
        'ffmpeg_source_sha256': sha(BASE / 'ffmpeg-7.0.2.tar.xz'),
        'backport_patch_sha256': sha(BASE / 'ffmpeg-7.0.2-av1-vt-backport.patch'),
        'avcodec_abi': '61.3.100 (original unchanged ABI)',
        'dav1d_headers': '1.2.1, matching original framework',
        'signature': 'ad-hoc integrity only; Sideloadly must provision and sign for device',
        'checks': {'avcodec_exports_preserved': len(original_exports),
                   'av1_videotoolbox_compiled': True,
                   'original_files_byte_identical': len(preserved),
                   'runner_executable_text_identical': True,
                   'mpv_byte_identical': sha(app / 'Frameworks/Mpv.framework/Mpv') == sha(original_app / 'Frameworks/Mpv.framework/Mpv'),
                   'avformat_byte_identical': sha(app / 'Frameworks/Avformat.framework/Avformat') == sha(original_app / 'Frameworks/Avformat.framework/Avformat'),
                   'avutil_byte_identical': sha(app / 'Frameworks/Avutil.framework/Avutil') == sha(original_app / 'Frameworks/Avutil.framework/Avutil'),
                   'deep_strict_signature': True, 'zip_integrity': True,
                   'patch_component_test_on_mac': {'frames': 64, 'hardware_frames': 64, 'software_fallback': False},
                   'iphone_installation_tested': False, 'iphone_playback_tested': False},
        'scope': 'Only Avcodec.framework executable and its Info.plist changed; app display name and root integrity signature updated (including Runner code-signature data, with executable text unchanged). Other original files preserved byte-for-byte.'
    }
    (BASE / '检查结果.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
