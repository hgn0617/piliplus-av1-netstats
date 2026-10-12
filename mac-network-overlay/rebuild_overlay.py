"""Rebuild the overlay for this saved Mac app; does not install or alter settings."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'PiliPlus AV1.app'
FRAMEWORK = APP / 'Contents/Frameworks/Mpv.framework'
VERSION = FRAMEWORK / 'Versions/A'
CORE = VERSION / 'MpvCore'
assert CORE.is_file(), 'This script requires the saved, already-patched MpvCore.'

subprocess.run([
    'clang', '-dynamiclib', '-arch', 'arm64', '-arch', 'x86_64',
    '-mmacosx-version-min=11.0', '-fobjc-arc', '-O2',
    str(ROOT / 'mpv_overlay_bridge.m'),
    '-framework', 'AppKit', '-framework', 'Foundation',
    '-Wl,-reexport_library,' + str(CORE),
    '-Wl,-install_name,@rpath/Mpv.framework/Versions/A/Mpv',
    '-Wl,-compatibility_version,2.0.0', '-Wl,-current_version,2.0.0',
    '-o', str(VERSION / 'Mpv'),
], check=True)
subprocess.run([
    'install_name_tool', '-change', '@rpath/Mpv.framework/Versions/A/MpvCore',
    '@loader_path/MpvCore', str(VERSION / 'Mpv'),
], check=True)
(VERSION / 'NetworkOverlay').mkdir(exist_ok=True)
(VERSION / 'NetworkOverlay/network_overlay.lua').write_bytes(
    (ROOT / 'network_overlay.lua').read_bytes())
subprocess.run(['codesign', '--force', '--sign', '-', str(VERSION / 'Mpv')], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(FRAMEWORK)], check=True)
subprocess.run([
    'codesign', '--force', '--sign', '-', '--entitlements',
    str(ROOT.parent / 'verification/original-entitlements.plist'), str(APP),
], check=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(APP)], check=True)
print('Rebuilt and signed:', APP)
