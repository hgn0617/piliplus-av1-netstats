"""Add a native OSD bridge to the user-confirmed working AV1 v2 IPA.

Preserve Avcodec and all other playback frameworks, and keep Runner's executable
code unchanged. Device provisioning/signing remains Sideloadly's responsibility.
"""
import hashlib
import argparse
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--stage-name', default='staging')
parser.add_argument('--output-name', default='PiliPlus_iOS_2.1.6+5472.ipa')
parser.add_argument(
    '--base-sha256',
    default='18e50f71cfe0c43adcaf1f4f3bd4e411ae8d1d0e653a63d6ccf43d01a82d95d3',
    help='SHA-256 of the already verified AV1 v2 IPA; required when rebuilding it with a new toolchain.',
)
args = parser.parse_args()
BASE = ROOT.parent / 'ios-build-v2'
SOURCE = BASE / 'PiliPlus_iOS_2.1.6+5472_AV1-v2.ipa'
STAGE = ROOT / args.stage_name
SDK = BASE / 'sdk-source/iPhoneOS18.5.sdk'
OUTPUT = ROOT / args.output_name


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr + result.stdout)
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(path):
    layout = run('otool', '-l', str(path))
    match = re.search(r'sectname __text\s+segname __TEXT\s+addr \S+\s+size (0x[0-9a-fA-F]+)\s+offset (\d+)', layout)
    assert match
    size, offset = int(match[1], 16), int(match[2])
    return hashlib.sha256(path.read_bytes()[offset:offset + size]).hexdigest()


def exports(path):
    return set(re.findall(r'^\s+(?:0x[0-9A-Fa-f]+|\[re-export\])\s+(_\S+)', run('xcrun', 'dyld_info', '-exports', str(path)), re.M))


assert sha(SOURCE) == args.base_sha256, (
    f'Base IPA hash mismatch: expected {args.base_sha256}, got {sha(SOURCE)}. '
    'Verify the AV1 v2 package before adding the overlay.'
)
assert not STAGE.exists(), 'Keep existing staging intact; use a new work directory to rebuild.'
with zipfile.ZipFile(SOURCE) as archive:
    assert archive.testzip() is None
    for entry in archive.infolist():
        rel = Path(entry.filename)
        mode = entry.external_attr >> 16
        assert not rel.is_absolute() and '..' not in rel.parts and not stat.S_ISLNK(mode)
        dest = STAGE / rel
        if entry.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(entry))
            os.chmod(dest, stat.S_IMODE(mode) or 0o644)

APP = STAGE / 'Payload/Runner.app'
FRAMEWORK = APP / 'Frameworks/Mpv.framework'
CORE_FRAMEWORK = APP / 'Frameworks/MpvCore.framework'
CORE_FRAMEWORK.mkdir()
CORE = CORE_FRAMEWORK / 'MpvCore'
preserved = {str(p.relative_to(APP)): sha(p) for p in APP.rglob('*') if p.is_file()
             and not p.is_relative_to(FRAMEWORK)
             and not p.is_relative_to(APP / '_CodeSignature')
             and p not in [APP / 'Runner', APP / 'Info.plist']}
original_text = text_sha(FRAMEWORK / 'Mpv')
runner_text = text_sha(APP / 'Runner')
original_exports = exports(FRAMEWORK / 'Mpv')
shutil.copy2(FRAMEWORK / 'Mpv', CORE)
run('install_name_tool', '-id', '@rpath/MpvCore.framework/MpvCore', str(CORE))
core_info = plistlib.loads((FRAMEWORK / 'Info.plist').read_bytes())
core_info.update(CFBundleExecutable='MpvCore', CFBundleIdentifier='com.github.media-kit.MpvCore',
                 CFBundleName='MpvCore', CFBundlePackageType='FMWK', CFBundleSupportedPlatforms=['iPhoneOS'])
(CORE_FRAMEWORK / 'Info.plist').write_bytes(plistlib.dumps(core_info, fmt=plistlib.FMT_BINARY))

compile_command = [
    'clang', '-dynamiclib', '-target', 'arm64-apple-ios15.0', '-isysroot', str(SDK),
    '-fobjc-arc', '-O2', str(ROOT / 'mpv_network_bridge.m'), '-framework', 'Foundation',
    '-Wl,-reexport_library,' + str(CORE),
    '-Wl,-install_name,@rpath/Mpv.framework/Mpv',
    '-Wl,-compatibility_version,2.0.0', '-Wl,-current_version,2.0.0',
    '-o', str(FRAMEWORK / 'Mpv'),
]
(ROOT / 'compile-command.json').write_text(json.dumps(compile_command, indent=2) + '\n')
run(*compile_command)
run('install_name_tool', '-change', '@rpath/MpvCore.framework/MpvCore',
    '@loader_path/../MpvCore.framework/MpvCore', str(FRAMEWORK / 'Mpv'))
os.chmod(FRAMEWORK / 'Mpv', 0o755)
wrapper_info = plistlib.loads((FRAMEWORK / 'Info.plist').read_bytes())
wrapper_info['MinimumOSVersion'] = '15.0'
(FRAMEWORK / 'Info.plist').write_bytes(plistlib.dumps(wrapper_info, fmt=plistlib.FMT_BINARY))

settings = APP / 'Settings.bundle'
assert not settings.exists(), 'Existing app settings must be merged, never replaced.'
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
app_info = plistlib.loads((APP / 'Info.plist').read_bytes())
app_info['CFBundleDisplayName'] = 'PiliPlus AV1 网速'
(APP / 'Info.plist').write_bytes(plistlib.dumps(app_info, fmt=plistlib.FMT_BINARY))
for path in [CORE_FRAMEWORK, FRAMEWORK, APP]:
    run('codesign', '--force', '--sign', '-', '--timestamp=none', str(path))
run('codesign', '--verify', '--deep', '--strict', str(APP))

assert original_exports <= exports(CORE) | exports(FRAMEWORK / 'Mpv')
assert text_sha(CORE) == original_text
assert text_sha(APP / 'Runner') == runner_text
for rel, digest in preserved.items():
    assert sha(APP / rel) == digest, 'Unexpected modification: ' + rel
for path in [CORE, FRAMEWORK / 'Mpv']:
    assert re.search(r'^\s+iOS\s+\d', run('xcrun', 'dyld_info', '-platform', str(path)), re.M)
    assert '/Users/' not in '\n'.join(run('otool', '-L', str(path)).splitlines()[1:])
assert '_piliplus_network_test_preferences' not in exports(FRAMEWORK / 'Mpv')
with zipfile.ZipFile(OUTPUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted((STAGE / 'Payload').rglob('*')):
        archive.write(path, str(path.relative_to(STAGE)))
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    assert archive.read('Payload/Runner.app/Frameworks/Avcodec.framework/Avcodec') == (BASE / 'staging/Payload/Runner.app/Frameworks/Avcodec.framework/Avcodec').read_bytes()

manifest = {
    'output': str(OUTPUT), 'sha256': sha(OUTPUT), 'size_bytes': OUTPUT.stat().st_size,
    'base': str(SOURCE), 'base_sha256': sha(SOURCE),
    'checks': {'working_v2_avcodec_byte_identical': True, 'original_mpv_code_identical': True,
               'runner_executable_code_identical': True, 'original_mpv_exports_preserved': len(original_exports),
               'other_original_files_byte_identical': len(preserved), 'deep_strict_signature': True,
               'zip_integrity': True, 'iphone_installation_tested': False, 'iphone_playback_tested': False},
    'signature': 'Ad-hoc integrity only; Sideloadly must sign both Mpv and MpvCore frameworks and provision the app.',
    'settings': 'Settings > Apps > PiliPlus AV1 网速',
    'scope': 'Original mpv binary moved into a separate MpvCore.framework with original executable code intact; Mpv.framework is now a thin API re-export bridge. Working AV1 v2 Avcodec and every other media framework preserved byte-for-byte. Adds Settings.bundle and updates app name/signature.'
}
(ROOT / '检查结果.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
