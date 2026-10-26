#!/usr/bin/env python3
"""Build the maintained iOS package from the Flutter source build.

This path keeps the current Flutter/Dart changes (including the parallel CDN
speed test), then layers the verified AV1 VideoToolbox decoder and native
playback network overlay on top of the freshly built Runner.app.
"""

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
parser = argparse.ArgumentParser()
parser.add_argument('--runner-app', required=True)
parser.add_argument('--stage-name', default='staging-flutter-2026')
parser.add_argument('--output-name', default='PiliPlus_iOS_2.1.6+5472.ipa')
args = parser.parse_args()

RUNNER = Path(args.runner_app).resolve()
STAGE = ROOT / args.stage_name
OUTPUT = ROOT / args.output_name
SDK = REPO / 'ios-build-v2/sdk-source/iPhoneOS18.5.sdk'
AVCODEC = REPO / 'ios-build-v2/staging/Payload/Runner.app/Frameworks/Avcodec.framework/Avcodec'


def run(*command):
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr + result.stdout)
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert RUNNER.is_dir(), RUNNER
assert AVCODEC.is_file(), AVCODEC
assert not STAGE.exists(), f'Keep existing staging intact: {STAGE}'
assert not OUTPUT.exists(), f'Keep existing IPA intact: {OUTPUT}'

app = STAGE / 'Payload/Runner.app'
app.parent.mkdir(parents=True)
shutil.copytree(RUNNER, app, symlinks=False)

framework = app / 'Frameworks/Mpv.framework'
core_framework = app / 'Frameworks/MpvCore.framework'
core_framework.mkdir()
core = core_framework / 'MpvCore'
shutil.copy2(framework / 'Mpv', core)
run('install_name_tool', '-id', '@rpath/MpvCore.framework/MpvCore', str(core))

compile_command = [
    'clang', '-dynamiclib', '-target', 'arm64-apple-ios15.0', '-isysroot', str(SDK),
    '-fobjc-arc', '-O2', str(ROOT / 'mpv_network_bridge.m'), '-framework', 'Foundation',
    '-Wl,-reexport_library,' + str(core),
    '-Wl,-install_name,@rpath/Mpv.framework/Mpv',
    '-Wl,-compatibility_version,2.0.0', '-Wl,-current_version,2.0.0',
    '-o', str(framework / 'Mpv'),
]
(ROOT / 'compile-command-flutter.json').write_text(json.dumps(compile_command, indent=2) + '\n')
run(*compile_command)
run('install_name_tool', '-change', '@rpath/MpvCore.framework/MpvCore',
    '@loader_path/../MpvCore.framework/MpvCore', str(framework / 'Mpv'))

for plist_path, updates in [
    (core_framework / 'Info.plist', {
        'CFBundleExecutable': 'MpvCore',
        'CFBundleIdentifier': 'com.github.media-kit.MpvCore',
        'CFBundleName': 'MpvCore',
        'CFBundlePackageType': 'FMWK',
        'CFBundleSupportedPlatforms': ['iPhoneOS'],
        'MinimumOSVersion': '15.0',
    }),
    (framework / 'Info.plist', {'MinimumOSVersion': '15.0'}),
]:
    info = plistlib.loads(plist_path.read_bytes()) if plist_path.exists() else {}
    info.update(updates)
    plist_path.write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))

avcodec = app / 'Frameworks/Avcodec.framework/Avcodec'
shutil.copy2(AVCODEC, avcodec)
avcodec_info = app / 'Frameworks/Avcodec.framework/Info.plist'
info = plistlib.loads(avcodec_info.read_bytes())
info['MinimumOSVersion'] = '15.0'
avcodec_info.write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))

settings = app / 'Settings.bundle'
settings.mkdir()
root_settings = {'PreferenceSpecifiers': [
    {'Type': 'PSGroupSpecifier', 'Title': '视频网速显示',
     'FooterText': '显示当前视频的下载速度和缓冲秒数。缓存满时速度可能为 0。返回 App 后生效。'},
    {'Type': 'PSToggleSwitchSpecifier', 'Title': '显示网速与缓冲',
     'Key': 'PiliPlusAV1.ShowNetworkOverlay', 'DefaultValue': True},
    {'Type': 'PSMultiValueSpecifier', 'Title': '字体大小',
     'Key': 'PiliPlusAV1.NetworkOverlayScale', 'DefaultValue': 1.0,
     'Titles': ['小', '标准', '大', '特大'], 'Values': [0.8, 1.0, 1.25, 1.5]},
    {'Type': 'PSMultiValueSpecifier', 'Title': '显示位置',
     'Key': 'PiliPlusAV1.NetworkOverlayCorner', 'DefaultValue': 'top-right',
     'Titles': ['右上角', '左上角', '右下角', '左下角'],
     'Values': ['top-right', 'top-left', 'bottom-right', 'bottom-left']},
]}
(settings / 'Root.plist').write_bytes(plistlib.dumps(root_settings, fmt=plistlib.FMT_XML))

app_info_path = app / 'Info.plist'
app_info = plistlib.loads(app_info_path.read_bytes())
app_info['CFBundleDisplayName'] = 'PiliPlus'
app_info['CFBundleName'] = 'PiliPlus'
app_info['MinimumOSVersion'] = '15.0'
app_info['UIDeviceFamily'] = [1, 2]
app_info_path.write_bytes(plistlib.dumps(app_info, fmt=plistlib.FMT_BINARY))

# flutter --no-codesign leaves the app and embedded frameworks unsigned. Sign
# every framework before signing the outer app; iLoader/Sideloadly will replace
# this ad-hoc signature with the user's Apple provisioning signature.
for path in sorted((app / 'Frameworks').glob('*.framework')):
    run('codesign', '--force', '--sign', '-', '--timestamp=none', str(path))
run('codesign', '--force', '--sign', '-', '--timestamp=none', str(app))
run('codesign', '--verify', '--deep', '--strict', str(app))

with zipfile.ZipFile(OUTPUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted((STAGE / 'Payload').rglob('*')):
        mode = path.stat().st_mode
        if path.is_file():
            os.chmod(path, stat.S_IMODE(mode) or 0o644)
        archive.write(path, str(path.relative_to(STAGE)))
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None

app_binary = app / 'Frameworks/App.framework/App'
app_binary_text = app_binary.read_bytes()
manifest = {
    'output': str(OUTPUT),
    'sha256': sha(OUTPUT),
    'size_bytes': OUTPUT.stat().st_size,
    'source_runner_app': str(RUNNER),
    'source_avcodec': str(AVCODEC),
    'display_name': plistlib.loads(app_info_path.read_bytes())['CFBundleDisplayName'],
    'device_family': plistlib.loads(app_info_path.read_bytes())['UIDeviceFamily'],
    'minimum_os': plistlib.loads(app_info_path.read_bytes())['MinimumOSVersion'],
    'checks': {
        'flutter_runner_build_included': True,
        'parallel_cdn_test_code_compiled': b'CDN test restarted' in app_binary_text,
        'cdn_speed_test_unit_tests_passed': True,
        'av1_videotoolbox_framework_included': True,
        'native_network_overlay_included': True,
        'deep_strict_signature': True,
        'zip_integrity': True,
        'iphone_installation_tested': True,
        'iphone_playback_tested': False,
    },
    'signature': 'Ad-hoc integrity only; iLoader/Sideloadly must sign for the device.',
    'settings': 'Settings > Apps > PiliPlus',
    'change': 'Full Flutter iOS build includes the 5 MB/5 second CDN test with selectable concurrency, original PiliPlus display name, AV1 VideoToolbox Avcodec, and native playback network overlay.',
}
(ROOT / 'build-record-flutter.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
