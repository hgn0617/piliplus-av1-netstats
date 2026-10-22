"""Replace only App.framework in an existing, AV1/overlay-patched Mac app."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(app):
    executable = plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleExecutable']
    return {
        str(p.relative_to(app)): sha(p)
        for p in app.rglob('*')
        if p.is_file() and not p.is_symlink()
        and not str(p.relative_to(app)).startswith((
            'Contents/Frameworks/App.framework/', 'Contents/_CodeSignature/',
        ))
        and p != app / 'Contents/MacOS' / executable
    }


def runner_code(app):
    executable = plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleExecutable']
    binary = app / 'Contents/MacOS' / executable
    result = {}
    with tempfile.TemporaryDirectory() as directory:
        for arch in run('lipo', '-archs', str(binary)).split():
            thin = Path(directory) / arch
            run('lipo', str(binary), '-thin', arch, '-output', str(thin))
            layout = run('otool', '-l', str(thin))
            match = re.search(r'sectname __text\s+segname __TEXT\s+addr \S+\s+size (0x[0-9a-fA-F]+)\s+offset (\d+)', layout)
            assert match
            size, offset = int(match[1], 16), int(match[2])
            result[arch] = hashlib.sha256(thin.read_bytes()[offset:offset + size]).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-app', type=Path, required=True)
    parser.add_argument('--flutter-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_app.resolve()
    output = args.output.resolve()
    flutter = args.flutter_output.resolve()
    assert source.is_dir() and not output.exists(), 'Use a new output path.'
    run('codesign', '--verify', '--deep', '--strict', str(source))
    info_path = 'Contents/Frameworks/FlutterMacOS.framework/Resources/Info.plist'
    old_engine = plistlib.loads((source / info_path).read_bytes())['FlutterEngine']
    new_engine = plistlib.loads((flutter / 'FlutterMacOS.framework/Resources/Info.plist').read_bytes())['FlutterEngine']
    assert old_engine == new_engine, 'Rebuild using the exact installed Flutter engine.'
    original = files(source)
    original_runner_code = runner_code(source)
    entitlements = subprocess.check_output(
        ['codesign', '-d', '--entitlements', ':-', str(source)], stderr=subprocess.DEVNULL,
    )
    plistlib.loads(entitlements)
    output.parent.mkdir(parents=True, exist_ok=True)
    run('ditto', str(source), str(output))
    app_framework = output / 'Contents/Frameworks/App.framework'
    shutil.rmtree(app_framework)
    run('ditto', str(flutter / 'App.framework'), str(app_framework))
    # Native hooks have the same package IDs/ABI as the locked original build.
    # Keep the original manifest and native libraries, just like all media libs.
    manifest_rel = 'Resources/flutter_assets/NativeAssetsManifest.json'
    old_manifest = source / 'Contents/Frameworks/App.framework' / manifest_rel
    new_manifest = app_framework / manifest_rel
    old = json.loads(old_manifest.read_text())
    new = json.loads(new_manifest.read_text())
    assert old == new, 'Native asset layout changed; inspect before replacing libraries.'
    entitlements_path = output.parent / 'original-entitlements.plist'
    entitlements_path.write_bytes(entitlements)
    run('codesign', '--force', '--sign', '-', str(app_framework))
    run('codesign', '--force', '--sign', '-', '--entitlements', str(entitlements_path), str(output))
    run('codesign', '--verify', '--deep', '--strict', str(output))
    assert files(output) == original, 'Unexpected modification outside App.framework.'
    assert runner_code(output) == original_runner_code, 'Runner executable code changed.'
    record = {
        'base_version': '2.1.6+5472 / 2.1.6.2',
        'base_commit': 'b2d6a5befb6dd292b9f7ad98794f3620f6dfb818',
        'flutter_version': '3.47.7', 'flutter_engine': old_engine,
        'sample_bytes': 5000000, 'wall_clock_limit_seconds': 5,
        'default_concurrency': 4, 'concurrency_choices': [1, 4, 8, 21],
        'app_framework_sha256': sha(app_framework / 'App'),
        'unchanged_files_outside_app_framework': len(original),
        'native_asset_manifest_unchanged': True,
        'existing_av1_and_overlay_runtime_unchanged': True,
        'runner_executable_text_unchanged': True,
        'runner_signature_updated': True,
        'deep_strict_signature': True,
    }
    (output.parent / 'bundle-verification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
