from pathlib import Path
import os
import unittest
from unittest.mock import patch
from fixture_support import fixture_temp, fixed_paths


class FixturePathTests(unittest.TestCase):
    def test_original_paths_are_replaced_once_not_recursively(self):
        base=Path('/tmp/example')
        text=fixed_paths('/proc/self /sys/block /tmp/stage',base,('/proc/','/sys/','/tmp/'))
        self.assertEqual(text,'/tmp/example/proc/self /tmp/example/sys/block /tmp/example/tmp/stage')

    def test_mountpoint_fields_and_nonmatching_paths_remain_unchanged(self):
        self.assertEqual(fixed_paths('none /tmp tmpfs rw /bin/mount /var/other',Path('/tmp/example'),('/proc/','/bin/mount')),
                         'none /tmp tmpfs rw /tmp/example/bin/mount /var/other')

    def test_fixture_base_ignores_spaced_workstation_tmpdir(self):
        with patch.dict(os.environ,{'TMPDIR':'/unavailable path with spaces'}),fixture_temp() as folder:
            self.assertFalse(any(character.isspace() for character in folder))
            self.assertEqual(Path(folder).stat().st_mode & 0o777,0o700)
