"""Run the recorded Avcodec link command after the static codec build."""
import json
from pathlib import Path
import subprocess


def main():
    base = Path(__file__).resolve().parent
    command = json.loads((base / 'link-command.json').read_text())
    assert (base / 'ffmpeg-7.0.2/libavcodec/libavcodec.a').exists()
    subprocess.run(command, cwd=base, check=True)
    print('Linked:', base / 'Avcodec-new')


if __name__ == '__main__':
    main()
