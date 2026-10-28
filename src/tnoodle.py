"""Run the local TNoodle CLI distribution for free-solving scrambles."""
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
LOCAL_EXECUTABLE = ROOT / 'data/tnoodle/tnoodle-cli-linux_x64/bin/tnoodle'


def generate():
    executable = os.environ.get('TNOODLE_BIN') or (
        str(LOCAL_EXECUTABLE) if LOCAL_EXECUTABLE.is_file() else shutil.which('tnoodle'))
    if not executable:
        raise ValueError('TNoodle is not installed. Run python3 scripts/install_tnoodle.py, then retry.')
    try:
        result = subprocess.run(
            [executable, 'scramble', '--puzzle', 'three', '--count', '1'],
            capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('TNoodle could not generate a scramble. Check its installation and retry.') from exc
    scramble = result.stdout.strip()
    if not re.fullmatch(r"[URFDLB](?:2|')?(?:\s+[URFDLB](?:2|')?)+", scramble):
        raise ValueError('TNoodle returned an invalid scramble. Check its installation and retry.')
    return ' '.join(scramble.split())
