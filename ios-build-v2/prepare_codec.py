"""Prepare a clean FFmpeg 7.0.2 AV1 VT build using an external iPhoneOS SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    root = base.parent
    sdk = args.sdk.resolve()
    assert (sdk / 'SDKSettings.json').is_file(), 'Specify an existing iPhoneOS SDK.'
    sdk_link = base / 'sdk-source/iPhoneOS18.5.sdk'
    sdk_link.parent.mkdir(exist_ok=True)
    if sdk_link.exists():
        assert sdk_link.resolve() == sdk, 'Existing SDK link points elsewhere.'
    else:
        sdk_link.symlink_to(sdk, target_is_directory=True)
    source = root / 'ios-check/PiliPlus_ios_2.1.6+5472.ipa'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '6cccd84c5459fbefeef2683659e7dbe3d65a76243862525d24238303d9a341ee'
    unpacked = root / 'ios-check/unpacked'
    assert not unpacked.exists(), 'Keep existing inputs intact; use a clean work directory.'
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        for entry in archive.infolist():
            rel = Path(entry.filename); mode = entry.external_attr >> 16
            assert not rel.is_absolute() and '..' not in rel.parts and not stat.S_ISLNK(mode)
            destination = unpacked / rel
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(entry))
                os.chmod(destination, stat.S_IMODE(mode) or 0o644)
    archive_path = base / 'ffmpeg-7.0.2.tar.xz'
    if not archive_path.exists():
        with urllib.request.urlopen('https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.xz', timeout=60) as response:
            archive_path.write_bytes(response.read())
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == '8646515b638a3ad303e23af6a3587734447cb8fc0a0c064ecdb8e95c4fd8b389'
    assert not (base / 'ffmpeg-7.0.2').exists(), 'Apply the patch only to clean FFmpeg sources.'
    subprocess.run(['tar', '-xf', str(archive_path), '-C', str(base)], check=True)
    subprocess.run(['patch', '-p1', '-i', str(base / 'ffmpeg-7.0.2-av1-vt-backport.patch')], cwd=base / 'ffmpeg-7.0.2', check=True)
    for name in ['configure-command', 'link-command', 'host-configure-command']:
        template = (base / (name + '.template.json')).read_text()
        value = json.loads(template)
        args_list = [item.replace('${WORKSPACE}', str(root)) for item in value]
        (base / (name + '.json')).write_text(json.dumps(args_list, indent=2) + '\n')
    frameworks = unpacked / 'Payload/Runner.app/Frameworks'
    pkgconfig = base / 'pkgconfig'; pkgconfig.mkdir(exist_ok=True)
    (pkgconfig / 'dav1d.pc').write_text(
        'Name: dav1d\nDescription: Original IPA dav1d framework\nVersion: 1.2.1\n'
        f'Libs: -F{frameworks} -framework Dav1d\n'
        f'Cflags: -I{base / "dav1d-headers"}\n')
    assert shutil.which('pkg-config'), 'pkg-config is required for configure.'
    print('Prepared clean FFmpeg source, original frameworks, SDK link and native configs.')


if __name__ == '__main__':
    main()
