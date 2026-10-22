"""Rebuild the CDN patch against the pinned upstream/Flutter source versions."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import unquote, urlparse


BASE_COMMIT = 'b2d6a5befb6dd292b9f7ad98794f3620f6dfb818'
ENGINE = 'deb287481e3ce9468f3434937ced4240a70539ca'


def run(args, cwd):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def apply_once(patch, directory):
    reverse = subprocess.run(
        ['git', 'apply', '--reverse', '--check', str(patch)],
        cwd=directory, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if reverse.returncode == 0:
        return
    run(['git', 'apply', '--check', patch], directory)
    run(['git', 'apply', patch], directory)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--flutter-sdk', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    sdk = args.flutter_sdk.resolve()
    root = Path(__file__).resolve().parent
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    assert commit == BASE_COMMIT, 'Use the pinned upstream 2.1.6.2 source.'
    assert (sdk / 'bin/internal/engine.version').read_text().strip() == ENGINE
    flutter = sdk / 'bin/flutter'
    apply_once(root / 'cdn-speed-5mb-5s.patch', source)
    # Follow upstream's macOS patch list; do not run its global Git config edits.
    script = (source / 'lib/scripts/patch.ps1').read_text()
    variables = dict(re.findall(r'\$(\w+)\s*=\s*"([^"]+\.patch)"', script))
    flutter_names = re.findall(r'\$(\w+)', re.search(r'\$patches = @\((.*?)\)\s*\n', script, re.S)[1])
    assert len(flutter_names) == 22
    for name in flutter_names:
        apply_once(source / variables[name], sdk)
    run([flutter, 'pub', 'get', '--enforce-lockfile'], source)
    packages = json.loads((source / '.dart_tool/package_config.json').read_text())['packages']
    material = next(p for p in packages if p['name'] == 'material_ui')
    material_root = Path(unquote(urlparse(material['rootUri']).path))
    material_names = re.findall(r'\$(\w+)', re.search(r'\$patches_material = @\((.*?)\)', script, re.S)[1])
    assert len(material_names) == 8
    for name in material_names:
        apply_once(source / variables[name], material_root)
    run([sdk / 'bin/dart', 'analyze', 'lib/utils/cdn_speed_test.dart',
         'lib/pages/setting/widgets/select_dialog.dart'], source)
    run([sdk / 'bin/dart', 'run', 'tool/verify_cdn_speed_test.dart'], source)
    config = {'pili.name': '2.1.6', 'pili.code': 5472,
              'pili.hash': BASE_COMMIT, 'pili.time': int(time.time())}
    (source / 'pili_release.json').write_text(json.dumps(config))
    defines = ','.join(base64.b64encode(f'{k}={v}'.encode()).decode() for k, v in config.items())
    run([flutter, 'assemble', '--output=build/cdn-release',
         '-dTargetPlatform=darwin', '-dBuildMode=release',
         '-dDarwinArchs=arm64 x86_64', '-dTreeShakeIcons=false',
         '-dDartDefines=' + defines, 'release_macos_bundle_flutter_assets'], source)
    print('Output:', source / 'build/cdn-release')


if __name__ == '__main__':
    main()
