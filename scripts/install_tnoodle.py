"""Install the pinned TNoodle CLI distribution and runtime locally (Linux x64)."""
import hashlib
import io
from pathlib import Path
import platform
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/SpeedcuberOSS/tnoodle-cli/releases/download/v1.1.1/tnoodle-cli-1.1.1-linux_x64.zip'
SHA256 = '32a3265ef8019367a16b05ac951ade3efdda45ceb48b6787a1f9560dcc1325fd'


def main():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise SystemExit('Install TNoodle CLI for your platform and set TNOODLE_BIN to its executable.')
    with urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('TNoodle download checksum did not match; nothing was installed.')
    destination = ROOT / 'data/tnoodle'
    with ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                raise SystemExit('Unsafe path in TNoodle archive.')
        archive.extractall(destination)
        for entry in archive.infolist():
            if entry.external_attr >> 16 & 0o111:
                path = destination / entry.filename
                path.chmod(path.stat().st_mode | 0o111)
    print('TNoodle CLI installed in', destination)


if __name__ == '__main__':
    main()
