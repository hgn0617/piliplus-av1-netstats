"""Prepare the saved-layout Mac app for rebuild_overlay.py."""
import argparse
from pathlib import Path
import plistlib
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    app = root / 'PiliPlus AV1.app'
    if app.exists():
        raise SystemExit('Output already exists; keep the previous build intact.')
    source = args.source.resolve()
    original = source / 'Contents/Frameworks/Mpv.framework/Versions/A/Mpv'
    assert original.is_file()
    assert not original.with_name('MpvCore').exists(), 'Provide the AV1 app before applying the overlay.'
    entitlements = subprocess.check_output(['codesign', '-d', '--entitlements', ':-', str(source)], stderr=subprocess.DEVNULL)
    plistlib.loads(entitlements)
    subprocess.run(['ditto', str(source), str(app)], check=True)
    version = app / 'Contents/Frameworks/Mpv.framework/Versions/A'
    (version / 'Mpv').rename(version / 'MpvCore')
    subprocess.run(['install_name_tool', '-id', '@rpath/Mpv.framework/Versions/A/MpvCore', str(version / 'MpvCore')], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(version / 'MpvCore')], check=True)
    path = root.parent / 'verification/original-entitlements.plist'
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(entitlements)
    print('Prepared:', app)


if __name__ == '__main__':
    main()
