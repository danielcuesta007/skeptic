"""The dependency check touches no network: npm and the file system are faked or temporary."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from website_deps import ensure_website_deps


class EnsureWebsiteDeps(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.website = Path(folder.name)
        self.calls = []

    def run_fake(self, command, **kwargs):
        self.calls.append((command, kwargs['cwd'], kwargs['check']))

    def ensure(self, which=lambda _: '/bin/npm', run=None):
        return ensure_website_deps(self.website, which=which, run=run or self.run_fake, log=lambda *a, **k: None)

    def test_existing_dependencies_are_left_alone(self):
        (self.website / 'node_modules').mkdir()
        (self.website / 'node_modules' / '.package-lock.json').touch()
        self.assertFalse(self.ensure())
        self.assertEqual(self.calls, [])

    def test_interrupted_install_is_installed_again(self):
        (self.website / 'node_modules').mkdir()
        self.assertTrue(self.ensure())
        self.assertEqual(len(self.calls), 1)

    def test_fresh_checkout_installs_the_locked_versions(self):
        self.assertTrue(self.ensure())
        self.assertEqual(self.calls, [(['npm', 'ci'], self.website, True)])

    def test_missing_npm_explains_what_to_do(self):
        with self.assertRaisesRegex(SystemExit, 'Node 22'):
            self.ensure(which=lambda _: None)
        self.assertEqual(self.calls, [])

    def test_failed_install_explains_what_to_do(self):
        def fail(*args, **kwargs):
            raise subprocess.CalledProcessError(1, 'npm')
        with self.assertRaisesRegex(SystemExit, 'npm ci --prefix apps/website'):
            self.ensure(run=fail)


if __name__ == '__main__':
    unittest.main()
