import subprocess
import unittest
from unittest.mock import patch

from src import tnoodle


class TNoodleTests(unittest.TestCase):
    @patch.dict('os.environ', {'TNOODLE_BIN': '/local/tnoodle'})
    @patch('src.tnoodle.subprocess.run')
    def test_generates_three_by_three_with_fixed_arguments(self, run):
        run.return_value.stdout = "R U2 F'\n"
        self.assertEqual(tnoodle.generate(), "R U2 F'")
        run.assert_called_once_with(
            ['/local/tnoodle', 'scramble', '--puzzle', 'three', '--count', '1'],
            capture_output=True, text=True, timeout=30, check=True)

    @patch.dict('os.environ', {'TNOODLE_BIN': '/local/tnoodle'})
    @patch('src.tnoodle.subprocess.run')
    def test_rejects_invalid_output_and_runtime_failures(self, run):
        for output in ['', 'Java error', 'R U2 bogus']:
            with self.subTest(output=output):
                run.return_value.stdout = output
                with self.assertRaisesRegex(ValueError, 'invalid scramble'):
                    tnoodle.generate()
        for error in [OSError(), subprocess.TimeoutExpired('tnoodle', 30),
                      subprocess.CalledProcessError(1, 'tnoodle')]:
            run.side_effect = error
            with self.assertRaisesRegex(ValueError, 'could not generate'):
                tnoodle.generate()

    @patch.dict('os.environ', {}, clear=True)
    @patch('src.tnoodle.shutil.which', return_value=None)
    @patch('src.tnoodle.LOCAL_EXECUTABLE')
    def test_missing_installation_explains_setup(self, executable, which):
        executable.is_file.return_value = False
        with self.assertRaisesRegex(ValueError, 'install_tnoodle.py'):
            tnoodle.generate()
