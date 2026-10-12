#!/usr/bin/env python3
"""Patch a separate PiliPlus copy with libmpv from an official IINA release."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def deps(binary):
    return [line.strip().split(' (compatibility version')[0]
            for line in run('otool', '-arch', 'arm64', '-L', str(binary)).splitlines()[1:]]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--iina', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; refusing to overwrite it.')
    run('codesign', '--verify', '--deep', '--strict', str(args.iina))
    original = args.source / 'Contents/Frameworks/Mpv.framework/Versions/A/Mpv'
    source_libs = args.iina / 'Contents/Frameworks'
    source_mpv = source_libs / 'libmpv.2.dylib'
    pending, closure = [source_mpv], {}
    while pending:
        binary = pending.pop()
        if binary.name in closure:
            continue
        closure[binary.name] = binary
        for dep in deps(binary):
            if dep.startswith(('/System/', '/usr/lib/')):
                continue
            dependency = source_libs / Path(dep).name
            if not dependency.is_file():
                raise RuntimeError(f'Unresolved dependency: {binary.name}: {dep}')
            pending.append(dependency)
    old_symbols = set(run('nm', '-arch', 'arm64', '-gU', str(original)).splitlines())
    new_names = {line.split()[-1] for line in run('nm', '-arch', 'arm64', '-gU', str(source_mpv)).splitlines() if line.split()}
    missing = sorted({line.split()[-1] for line in old_symbols
                      if line.split() and line.split()[-1].startswith('_mpv_')} - new_names)
    if missing:
        raise RuntimeError(f'Missing original mpv C API symbols: {missing}')
    entitlements = subprocess.check_output(
        ['codesign', '-d', '--entitlements', ':-', str(args.source)], stderr=subprocess.DEVNULL)
    plistlib.loads(entitlements)
    run('ditto', str(args.source), str(args.output))
    target = args.output / 'Contents/Frameworks/Mpv.framework/Versions/A/Mpv'
    runtime = target.parent / 'AV1Runtime'
    runtime.mkdir()
    target.unlink()
    shutil.copy2(source_mpv, target)
    mapping = {source_mpv.name: target}
    for name, binary in sorted(closure.items()):
        if binary == source_mpv:
            continue
        destination = runtime / name
        shutil.copy2(binary, destination)
        mapping[name] = destination
    for name, binary in mapping.items():
        binary.chmod(0o755)
        identity = ('@rpath/Mpv.framework/Versions/A/Mpv' if binary == target
                    else '@rpath/Mpv.framework/Versions/A/AV1Runtime/' + name)
        changes = ['install_name_tool', '-id', identity]
        for dep in deps(binary):
            if dep.startswith(('/System/', '/usr/lib/')):
                continue
            basename = Path(dep).name
            if basename == source_mpv.name:
                replacement = '@loader_path/../Mpv' if binary != target else identity
            else:
                replacement = ('@loader_path/AV1Runtime/' if binary == target else '@loader_path/') + basename
            changes += ['-change', dep, replacement]
        changes += [str(binary)]
        run(*changes)
        run('codesign', '--force', '--sign', '-', str(binary))
    info_path = args.output / 'Contents/Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    info['CFBundleName'] = 'PiliPlus AV1'
    info['CFBundleDisplayName'] = 'PiliPlus AV1'
    info_path.write_bytes(plistlib.dumps(info))
    entitlement_file = args.output.parent / 'verification/original-entitlements.plist'
    entitlement_file.parent.mkdir(exist_ok=True)
    entitlement_file.write_bytes(entitlements)
    run('codesign', '--force', '--sign', '-', str(target.parent.parent.parent))
    run('codesign', '--force', '--sign', '-', '--entitlements', str(entitlement_file), str(args.output))
    run('codesign', '--verify', '--deep', '--strict', str(args.output))
    manifest = {
        'source_app': str(args.source), 'patched_app': str(args.output),
        'iina_release': 'https://github.com/iina/iina/releases/tag/v1.5.0',
        'original_mpv_sha256': digest(original),
        'source_mpv_sha256': digest(source_mpv),
        'patched_mpv_sha256': digest(target),
        'original_mpv_api_symbols_missing': missing,
        'runtime_libraries': {name: digest(path) for name, path in sorted(mapping.items())},
        'bundle_identifier': info['CFBundleIdentifier'],
    }
    (entitlement_file.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({'output': str(args.output), 'native_libraries': len(mapping), 'signature_verified': True}))


if __name__ == '__main__':
    main()
