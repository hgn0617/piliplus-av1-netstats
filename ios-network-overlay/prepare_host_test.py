"""Compile the iOS overlay source for Mac playback/render component tests."""
import argparse
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-app', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    host = root / 'host-test'
    assert not host.exists(), 'Keep previous host tests intact.'
    wrapper = host / 'Mpv.framework'; core = host / 'MpvCore.framework'
    wrapper.mkdir(parents=True); core.mkdir()
    original = args.source_app.resolve() / 'Contents/Frameworks/Mpv.framework/Versions/A'
    source = original / ('MpvCore' if (original / 'MpvCore').exists() else 'Mpv')
    assert (original / 'AV1Runtime').is_dir(), 'Provide the IINA-runtime AV1 Mac app.'
    shutil.copy2(source, core / 'MpvCore')
    shutil.copytree(original / 'AV1Runtime', core / 'AV1Runtime')
    subprocess.run(['install_name_tool', '-id', '@rpath/MpvCore.framework/MpvCore', str(core / 'MpvCore')], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(core / 'MpvCore')], check=True)
    command = ['clang', '-dynamiclib', '-arch', 'arm64', '-mmacosx-version-min=11.0', '-fobjc-arc', '-O2',
               str(root / 'mpv_network_bridge.m'), '-framework', 'Foundation',
               '-Wl,-reexport_library,' + str(core / 'MpvCore'),
               '-Wl,-install_name,@rpath/Mpv.framework/Mpv', '-Wl,-compatibility_version,2.0.0',
               '-o', str(wrapper / 'Mpv')]
    subprocess.run(command, check=True)
    subprocess.run(['install_name_tool', '-change', '@rpath/MpvCore.framework/MpvCore',
                    '@loader_path/../MpvCore.framework/MpvCore', str(wrapper / 'Mpv')], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(wrapper / 'Mpv')], check=True)
    print('Host component framework prepared. This does not test an iPhone app.')


if __name__ == '__main__':
    main()
