"""Test update and install commands with local repositories and temporary homes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
REPOS = ('pond-interface', 'vicinae', 'package-manager')


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pond-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_STATE_HOME=str(self.home / '.local/state'),
                        XDG_CONFIG_HOME=str(self.home / '.config'),
                        GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Pond test', GIT_AUTHOR_EMAIL='pond@example.invalid',
                        GIT_COMMITTER_NAME='Pond test', GIT_COMMITTER_EMAIL='pond@example.invalid',
                        GIT_TERMINAL_PROMPT='0')
        tools = self.root / 'fedora-tools'
        (tools / 'bin').mkdir(parents=True)
        shutil.copy2(TOOLS / 'pond', tools / 'pond')
        shutil.copy2(TOOLS / 'bin/install-shell', tools / 'bin/install-shell')

    def run_command(self, *args):
        return subprocess.run(args, env=self.env, cwd=self.root, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)

    def git(self, repo, *args):
        result = self.run_command('git', '-C', str(repo), *args)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout.strip()

    def commit(self, repo, path, text):
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        self.git(repo, 'add', '--', path)
        self.git(repo, 'commit', '-m', 'Test change')
        return self.git(repo, 'rev-parse', 'HEAD')

    def setup_sources(self):
        for name in REPOS:
            origin = self.root / 'origins' / name
            origin.mkdir(parents=True)
            self.git(origin, 'init', '-b', 'main')
            self.commit(origin, 'shell/main.qml', 'original\n')
            self.git(self.root, 'clone', str(origin), name)
        self.git(self.root / 'pond-interface', 'switch', '-c', 'fedora')
        self.commit(self.root / 'pond-interface', 'shell/local.qml', 'local feature\n')

    def advance_origins(self):
        for name in REPOS:
            self.commit(self.root / 'origins' / name, 'shell/new.qml', 'upstream feature\n')

    def heads(self):
        return {name: self.git(self.root / name, 'rev-parse', 'HEAD') for name in REPOS}

    def pond(self, *args):
        return self.run_command(str(self.root / 'fedora-tools/pond'), *args)

    def test_update_rebases_local_feature_and_fast_forwards_other_sources(self):
        self.setup_sources()
        self.advance_origins()
        result = self.pond('update')
        self.assertEqual(result.returncode, 0, result.stdout)
        for name in REPOS:
            self.assertTrue((self.root / name / 'shell/new.qml').is_file())
        self.assertEqual((self.root / 'pond-interface/shell/local.qml').read_text(), 'local feature\n')
        for name in REPOS[1:]:
            self.assertEqual(self.git(self.root / name, 'rev-parse', 'HEAD'),
                             self.git(self.root / 'origins' / name, 'rev-parse', 'HEAD'))

    def test_diverged_launcher_stops_before_any_source_head_changes(self):
        self.setup_sources()
        self.commit(self.root / 'vicinae', 'local.txt', 'local launcher change\n')
        self.advance_origins()
        before = self.heads()
        result = self.pond('update')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.heads(), before)

    def test_detached_head_stops_before_update(self):
        self.setup_sources()
        self.git(self.root / 'pond-interface', 'checkout', '--detach')
        self.advance_origins()
        before = self.heads()
        result = self.pond('update')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.heads(), before)

    def test_update_check_fetches_without_changing_source_heads(self):
        self.setup_sources()
        self.advance_origins()
        before = self.heads()
        result = self.pond('update', '--check')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.heads(), before)
        for name in REPOS:
            self.assertEqual(self.git(self.root / name, 'rev-parse', 'origin/main'),
                             self.git(self.root / 'origins' / name, 'rev-parse', 'HEAD'))
        self.assertIn('upstream', result.stdout)

    def test_dirty_source_stops_before_any_source_head_changes(self):
        self.setup_sources()
        (self.root / 'package-manager/untracked.txt').write_text('keep\n')
        self.advance_origins()
        before = self.heads()
        result = self.pond('update')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.heads(), before)

    def test_unfinished_bisect_stops_update_even_with_clean_files(self):
        self.setup_sources()
        self.git(self.root / 'vicinae', 'bisect', 'start')
        self.advance_origins()
        before = self.heads()
        result = self.pond('update')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('Unfinished Git operation in vicinae', result.stdout)
        self.assertEqual(self.heads(), before)

    def test_update_check_allows_local_edits(self):
        self.setup_sources()
        edited = self.root / 'pond-interface/shell/main.qml'
        edited.write_text('work in progress\n')
        self.advance_origins()
        before = self.heads()
        result = self.pond('update', '--check')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.heads(), before)
        self.assertEqual(edited.read_text(), 'work in progress\n')

    def test_unknown_update_option_is_rejected(self):
        result = self.pond('update', '--unknown')
        self.assertEqual(result.returncode, 2, result.stdout)

    def install_shell(self):
        return self.run_command(str(self.root / 'fedora-tools/bin/install-shell'))

    def target(self):
        return Path(self.env['XDG_CONFIG_HOME'] or self.home / '.config') / 'quickshell/pond-shell'

    def manifest(self):
        return Path(self.env['XDG_STATE_HOME']) / 'pond-fedora/shell-manifest.json'

    def test_install_updates_managed_files_and_preserves_extra_files(self):
        self.setup_sources()
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        (self.target() / 'extra.qml').write_text('user setting\n')
        self.commit(self.root / 'pond-interface', 'shell/main.qml', 'new version\n')
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.target() / 'main.qml').read_text(), 'new version\n')
        self.assertEqual((self.target() / 'extra.qml').read_text(), 'user setting\n')
        self.assertIn('main.qml', json.loads(self.manifest().read_text()))

    def test_install_conflict_does_not_write_other_files_or_manifest(self):
        self.setup_sources()
        self.assertEqual(self.install_shell().returncode, 0)
        manifest = self.manifest().read_bytes()
        (self.target() / 'main.qml').write_text('user change\n')
        self.commit(self.root / 'pond-interface', 'shell/local.qml', 'updated local feature\n')
        result = self.install_shell()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.target() / 'local.qml').read_text(), 'local feature\n')
        self.assertEqual(self.manifest().read_bytes(), manifest)

    def test_install_refuses_symlink_parent_before_writing_any_files(self):
        self.setup_sources()
        self.commit(self.root / 'pond-interface', 'shell/nested/new.qml', 'new file\n')
        outside = self.root / 'outside'
        outside.mkdir()
        self.target().mkdir(parents=True)
        (self.target() / 'nested').symlink_to(outside, target_is_directory=True)
        result = self.install_shell()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((outside / 'new.qml').exists())
        self.assertFalse((self.target() / 'main.qml').exists())
        self.assertFalse(self.manifest().exists())

    def test_install_uses_xdg_config_home(self):
        self.setup_sources()
        self.env['XDG_CONFIG_HOME'] = str(self.home / 'custom-config')
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.target() / 'main.qml').is_file())
        self.assertFalse((self.home / '.config/quickshell/pond-shell').exists())

    def test_install_uses_default_when_xdg_config_home_is_empty(self):
        self.setup_sources()
        self.env['XDG_CONFIG_HOME'] = ''
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.target() / 'main.qml').is_file())

    def test_install_keeps_independent_history_for_each_config_home(self):
        self.setup_sources()
        default_config = self.env['XDG_CONFIG_HOME']
        self.assertEqual(self.install_shell().returncode, 0)
        self.env['XDG_CONFIG_HOME'] = str(self.home / 'custom-config')
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.commit(self.root / 'pond-interface', 'shell/main.qml', 'new version\n')
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.target() / 'main.qml').read_text(), 'new version\n')
        self.env['XDG_CONFIG_HOME'] = default_config
        result = self.install_shell()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.target() / 'main.qml').read_text(), 'new version\n')


if __name__ == '__main__':
    unittest.main()
