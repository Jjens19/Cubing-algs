import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.release import bump, is_code, release


class ReleaseTests(unittest.TestCase):
    def test_version_policy(self):
        self.assertEqual(bump('0.1.0', ['fix: preserve progress']), '0.1.1')
        self.assertEqual(bump('0.1.1', ['feat(practice): add hints']), '0.2.0')
        self.assertEqual(bump('0.2.0', ['feat!: replace storage']), '1.0.0')
        self.assertEqual(bump('1.2.3', ['change storage\n\nBREAKING CHANGE: new format']), '2.0.0')
        for path in ['README.md', 'docs/screenshots/library.png', 'changelog/0.1.0.md', 'VERSION', '.github/release-state.json']:
            self.assertFalse(is_code(path), path)
        for path in ['app.py', 'src/static/app.js', 'requirements.txt', '.github/workflows/version.yml', 'src/static/cases/ell/ell-A1.svg']:
            self.assertTrue(is_code(path), path)

    def test_release_sequence(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                def git(*args):
                    return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL, text=True).strip()
                git('init', '-b', 'main')
                git('config', 'user.name', 'Release test')
                git('config', 'user.email', 'test@example.com')
                def commit(subject):
                    git('add', '.')
                    git('commit', '-m', subject)
                    return git('rev-parse', 'HEAD')
                Path('README.md').write_text('Project\n')
                before = commit('docs: initial README')
                Path('app.py').write_text('print("hello")\n')
                Path('VERSION').write_text('0.1.0\n')
                first = commit('feat: create app')
                with contextlib.redirect_stdout(io.StringIO()):
                    release(before, first)
                self.assertEqual(Path('VERSION').read_text().strip(), '0.1.0')
                self.assertIn('create app', Path('changelog/0.1.0.md').read_text())
                commit('chore(release): v0.1.0')
                Path('README.md').write_text('Updated docs\n')
                docs = commit('docs: update README')
                with contextlib.redirect_stdout(io.StringIO()):
                    release(first, docs)
                self.assertEqual(Path('VERSION').read_text().strip(), '0.1.0')
                Path('app.py').write_text('print("fixed")\n')
                fix = commit('fix: correct behavior')
                with contextlib.redirect_stdout(io.StringIO()):
                    release(docs, fix)
                self.assertEqual(Path('VERSION').read_text().strip(), '0.1.1')
                self.assertNotIn('update README', Path('changelog/0.1.1.md').read_text())
                # Retrying the same completed push must not bump twice.
                with contextlib.redirect_stdout(io.StringIO()):
                    release(docs, fix)
                self.assertEqual(Path('VERSION').read_text().strip(), '0.1.1')
                commit('chore(release): v0.1.1')
                Path('app.py').write_text('print("feature")\n')
                feature = commit('feat: add practice mode')
                with contextlib.redirect_stdout(io.StringIO()):
                    release(fix, feature)
                self.assertEqual(Path('VERSION').read_text().strip(), '0.2.0')
                self.assertTrue(Path('changelog/0.2.0.md').exists())
            finally:
                os.chdir(original)
