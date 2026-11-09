#!/usr/bin/env python3
"""Exercise patch setup in disposable repositories; no Android build required."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SETUP = Path(os.environ.get('PATCH_SETUP', Path(__file__).resolve().parents[2] / 'vendorsetup.sh'))

class PatchSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='patch-setup-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'android tree'
        self.repo = self.root / 'frameworks/base'
        self.repo.mkdir(parents=True)
        self.patches = self.root / 'vendor/extraPatches/patches/frameworks,base'
        self.patches.mkdir(parents=True)
        shutil.copyfile(SETUP, self.patches.parents[1] / 'vendorsetup.sh')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Patch tests')
        self.git('config', 'user.email', 'patch-tests@localhost')
        self.file = self.repo / 'value.txt'
        self.file.write_text('base\n')
        self.commit('base')
        self.base = self.git('rev-parse', 'HEAD')
        for number, value in enumerate(('one', 'two'), 1):
            self.file.write_text(value + '\n')
            self.commit('Change to ' + value)
            mail = self.git('format-patch', '-1', '--stdout')
            (self.patches / f'{number:04}.patch').write_text(mail + '\n')
        self.git('checkout', '-q', '--detach', self.base)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True, stderr=subprocess.PIPE).strip()

    def commit(self, title):
        self.git('add', '.')
        self.git('commit', '-qm', title)

    def setup(self):
        env = dict(os.environ, TEST_ROM_ROOT=str(self.root), TEST_START_DIR=self.tmp.name)
        command = '''gettop() { printf '%s\\n' "$TEST_ROM_ROOT"; }
cd "$TEST_START_DIR"
source "$TEST_ROM_ROOT/vendor/extraPatches/vendorsetup.sh"
result=$?
[ "$PWD" = "$TEST_START_DIR" ] || exit 88
exit "$result"
'''
        return subprocess.run(['bash', '-c', command], env=env, capture_output=True, text=True)

    def test_first_apply_rerun_and_new_patch(self):
        self.assertEqual(self.setup().returncode, 0)
        self.assertEqual(self.file.read_text(), 'two\n')
        head = self.git('rev-parse', 'HEAD')
        self.assertEqual(self.setup().returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        # Existing patches must not prevent a newly added patch from applying.
        self.file.write_text('three\n')
        self.commit('Change to three')
        (self.patches / '0003.patch').write_text(self.git('format-patch', '-1', '--stdout') + '\n')
        self.git('checkout', '-q', '--detach', head)
        self.assertEqual(self.setup().returncode, 0)
        self.assertEqual(self.file.read_text(), 'three\n')

    def test_dirty_target_preserved(self):
        self.file.write_text('local edit\n')
        self.assertNotEqual(self.setup().returncode, 0)
        self.assertEqual(self.file.read_text(), 'local edit\n')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)

    def test_failure_aborts_only_own_session(self):
        self.file.write_text('upstream conflict\n')
        self.commit('upstream')
        head = self.git('rev-parse', 'HEAD')
        self.assertNotEqual(self.setup().returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.file.read_text(), 'upstream conflict\n')
        self.assertFalse(Path(self.git('rev-parse', '--absolute-git-dir'), 'rebase-apply').exists())

    def test_existing_am_is_preserved(self):
        self.file.write_text('conflict\n')
        self.commit('upstream')
        failed = subprocess.run(['git', 'am', str(self.patches / '0001.patch')], cwd=self.repo, capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        session = Path(self.git('rev-parse', '--absolute-git-dir'), 'rebase-apply')
        before = (session / 'patch').read_bytes()
        self.assertNotEqual(self.setup().returncode, 0)
        self.assertEqual((session / 'patch').read_bytes(), before)

    def test_missing_repository_is_not_applied_to_parent(self):
        other = self.patches.parent / 'frameworks,missing'
        other.mkdir()
        shutil.copyfile(self.patches / '0001.patch', other / '0001.patch')
        self.assertNotEqual(self.setup().returncode, 0)
        self.assertFalse((self.root / 'value.txt').exists())

if __name__ == '__main__':
    unittest.main()
