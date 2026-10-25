"""Create release metadata for code changes on main; called by GitHub Actions."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo


def git(*args):
    return subprocess.check_output(['git', *args], input='', text=True).strip()


def is_code(path):
    file = Path(path)
    return not (file.suffix.lower() == '.md' or path.startswith(('docs/', 'changelog/'))
                or path in ('VERSION', '.github/release-state.json'))


def bump(version, messages):
    major, minor, patch = map(int, version.split('.'))
    if any(re.search(r'^[\w-]+(?:\([^\n]*\))?!:', message) or
           re.search(r'^BREAKING[ -]CHANGE:', message, re.M) for message in messages):
        return f'{major + 1}.0.0'
    if any(re.match(r'^feat(?:\([^\n]*\))?:', message) for message in messages):
        return f'{major}.{minor + 1}.0'
    return f'{major}.{minor}.{patch + 1}'


def output(**values):
    for key, value in values.items():
        print(f'{key}={value}')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            for key, value in values.items():
                stream.write(f'{key}={value}\n')


def release(before, after):
    state_file = Path('.github/release-state.json')
    state = json.loads(state_file.read_text()) if state_file.exists() else None
    if state and subprocess.run(['git', 'merge-base', '--is-ancestor', after, state['source_commit']], check=False).returncode == 0:
        output(released='false')
        return
    # Catch up from the last release if several pushes arrived while Actions ran.
    base = state['source_commit'] if state else before
    initial = set(base) == {'0'}
    if initial:
        base = git('hash-object', '-t', 'tree', '--stdin')
    changed = git('diff', '--name-only', base, after).splitlines()
    if not any(is_code(path) for path in changed):
        output(released='false')
        return
    commits = git('rev-list', '--reverse', after, *( [] if initial else ['^' + base])).splitlines()
    messages, notes = [], []
    for commit in commits:
        paths = git('diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-m', commit).splitlines()
        if not any(is_code(path) for path in paths):
            continue
        message = git('show', '-s', '--format=%B', commit)
        messages.append(message)
        # Escape Markdown syntax so commit subjects render as plain text.
        subject = re.sub(r'([\\`*_[\]<>])', r'\\\1', message.splitlines()[0])
        notes.append(f'- {subject} (`{commit[:7]}`)')
    version = bump(Path('VERSION').read_text().strip(), messages) if state else '0.1.0'
    date = datetime.now(ZoneInfo('Europe/Copenhagen')).date().isoformat()
    directory = Path('changelog')
    directory.mkdir(exist_ok=True)
    (directory / f'{version}.md').write_text(f'# {version} — {date}\n\n' + '\n'.join(notes) + '\n')
    Path('VERSION').write_text(version + '\n')
    index = Path('CHANGELOG.md')
    existing = index.read_text() if index.exists() else '# Changelog\n\nCode releases are listed here, newest first.\n'
    intro, separator, entries = existing.partition('\n## Releases\n')
    index.write_text(intro.rstrip() + '\n\n## Releases\n\n' + f'- [{version}](changelog/{version}.md) — {date}\n' + entries.lstrip())
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps({'version': version, 'source_commit': after}, indent=2) + '\n')
    output(released='true', version=version)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    args = parser.parse_args()
    release(args.before, args.after)
