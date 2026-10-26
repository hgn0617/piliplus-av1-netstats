#!/usr/bin/env python3
"""Combine a latest-main Flutter macOS build with the verified AV1 runtime."""

import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--source-app', type=Path, required=True)
parser.add_argument('--runtime-app', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--upstream-commit', required=True)
args = parser.parse_args()

source = args.source_app.resolve()
runtime_app = args.runtime_app.resolve()
output = args.output.resolve()
assert source.is_dir() and runtime_app.is_dir() and not output.exists()
run('codesign', '--verify', '--deep', '--strict', str(source))
run('codesign', '--verify', '--deep', '--strict', str(runtime_app))

source_mpv = source / 'Contents/Frameworks/Mpv.framework/Versions/A/Mpv'
runtime_version = runtime_app / 'Contents/Frameworks/Mpv.framework/Versions/A'
runtime_core = runtime_version / 'MpvCore'
runtime_libs = runtime_version / 'AV1Runtime'
assert source_mpv.is_file() and runtime_core.is_file() and runtime_libs.is_dir()

source_exports = {
    line.split()[-1]
    for line in run('nm', '-arch', 'arm64', '-gU', str(source_mpv)).splitlines()
    if '_mpv_' in line
}
runtime_exports = {
    line.split()[-1]
    for line in run('nm', '-arch', 'arm64', '-gU', str(runtime_core)).splitlines()
    if '_mpv_' in line
}
assert source_exports <= runtime_exports, sorted(source_exports - runtime_exports)

output.parent.mkdir(parents=True, exist_ok=True)
run('ditto', str(source), str(output))
version = output / 'Contents/Frameworks/Mpv.framework/Versions/A'
target = version / 'Mpv'
core = version / 'MpvCore'
runtime = version / 'AV1Runtime'
if target.exists():
    target.unlink()
if core.exists():
    core.unlink()
if runtime.exists():
    shutil.rmtree(runtime)
shutil.copy2(runtime_core, core)
shutil.copytree(runtime_libs, runtime)
core.chmod(0o755)
target.parent.mkdir(exist_ok=True)

compile_command = [
    'clang', '-dynamiclib', '-arch', 'arm64', '-arch', 'x86_64',
    '-mmacosx-version-min=11.0', '-fobjc-arc', '-O2',
    str(ROOT / 'mpv_overlay_bridge.m'), '-framework', 'AppKit', '-framework', 'Foundation',
    '-Wl,-reexport_library,' + str(core),
    '-Wl,-install_name,@rpath/Mpv.framework/Versions/A/Mpv',
    '-Wl,-compatibility_version,2.0.0', '-Wl,-current_version,2.0.0',
    '-o', str(target),
]
(ROOT / 'compile-command-latest.json').write_text(json.dumps(compile_command, indent=2) + '\n')
subprocess.run(compile_command, check=True)
subprocess.run([
    'install_name_tool', '-change', '@rpath/Mpv.framework/Versions/A/MpvCore',
    '@loader_path/MpvCore', str(target),
], check=True)
(version / 'NetworkOverlay').mkdir(exist_ok=True)
(version / 'NetworkOverlay/network_overlay.lua').write_bytes(
    (ROOT / 'network_overlay.lua').read_bytes())

info_path = output / 'Contents/Info.plist'
info = plistlib.loads(info_path.read_bytes())
info['CFBundleName'] = 'PiliPlus AV1'
info['CFBundleDisplayName'] = 'PiliPlus AV1'
info_path.write_bytes(plistlib.dumps(info))

entitlements = subprocess.check_output(
    ['codesign', '-d', '--entitlements', ':-', str(source)], stderr=subprocess.DEVNULL)
entitlements_path = output.parent / 'latest-main-entitlements.plist'
entitlements_path.write_bytes(entitlements)
for path in sorted(runtime.glob('*')):
    if path.is_file():
        subprocess.run(['codesign', '--force', '--sign', '-', str(path)], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(core)], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(target)], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(version.parent.parent)], check=True)
subprocess.run([
    'codesign', '--force', '--sign', '-', '--entitlements', str(entitlements_path), str(output),
], check=True)
run('codesign', '--verify', '--deep', '--strict', str(output))

record = {
    'output': str(output),
    'upstream_commit': args.upstream_commit,
    'flutter_engine': plistlib.loads((output / 'Contents/Frameworks/FlutterMacOS.framework/Resources/Info.plist').read_bytes())['FlutterEngine'],
    'source_flutter_app_sha256': sha(source / 'Contents/Frameworks/App.framework/App'),
    'runtime_core_sha256': sha(core),
    'native_runtime_libraries': len(list(runtime.glob('*'))),
    'mpv_api_symbols_preserved': len(source_exports),
    'display_name': info['CFBundleDisplayName'],
    'deep_strict_signature': True,
    'cdn_speed_test_source_rebuilt': True,
    'av1_runtime_reused_from_verified_app': True,
    'mac_runtime_playback_tested': False,
}
(output.parent / 'latest-main-verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
