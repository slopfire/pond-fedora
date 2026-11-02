"""Check SDDM theme installation planning without touching the host."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'bin/install-dm'
loader = importlib.machinery.SourceFileLoader('pond_install_dm', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
dm = importlib.util.module_from_spec(spec)
loader.exec_module(dm)


class InstallDmTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pond-dm-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        for name in ('lockscreen/greeter/Main.qml', 'lockscreen/greeter/metadata.desktop',
                     'lockscreen/frontend/Screen.qml', 'shell/assets/fonts/IBMPlexSerif-Regular.ttf',
                     'shell/assets/fonts/OFL-IBM-Plex.txt'):
            self.write(self.source / name, 'fixture')
        for name in ('System/qmldir', 'System/libpond_systemplugin.so', 'System/libpond_system.so',
                     'Daylight/qmldir', 'Daylight/Sky.qml', 'Daylight/SkyState.js',
                     'Daylight/sky.frag.qsb'):
            self.write(self.root / 'usr/lib64/qt6/qml/Pond' / name, 'fixture')
        (self.root / 'usr/local/share').mkdir(parents=True)
        (self.root / 'etc/sddm.conf.d').mkdir(parents=True)
        link = self.root / 'etc/systemd/system/display-manager.service'
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to('/usr/lib/systemd/system/plasmalogin.service')
        self.uid = os.getuid()

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def plan(self):
        return dm.prepare(self.source, self.root, self.uid)

    def test_earlier_theme_does_not_block_drop_in(self):
        self.write(self.root / 'etc/sddm.conf.d/theme.conf', '[Theme]\nCurrent=astronaut\n')
        target, config, files = self.plan()
        self.assertEqual(config.name, 'zz-pond-fedora.conf')
        self.assertEqual(len(files), 5)
        self.assertFalse(target.exists())

    def test_main_config_override_blocks_install(self):
        self.write(self.root / 'etc/sddm.conf', '[Theme]\nCurrent=other\n')
        with self.assertRaisesRegex(SystemExit, 'override'):
            self.plan()

    def test_later_drop_in_override_blocks_install(self):
        self.write(self.root / 'etc/sddm.conf.d/zzz-local', '[Theme]\nThemeDir=/elsewhere\n')
        with self.assertRaisesRegex(SystemExit, 'Conflicting'):
            self.plan()

    def test_unmanaged_theme_or_config_is_not_overwritten(self):
        self.write(self.root / 'usr/local/share/pond-dm/other', 'user data')
        with self.assertRaisesRegex(SystemExit, 'differs'):
            self.plan()

    def test_unsafe_source_is_rejected(self):
        link = self.source / 'lockscreen/frontend/extra.qml'
        link.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(SystemExit, 'non-regular'):
            self.plan()

    def test_writable_module_is_rejected(self):
        module = self.root / 'usr/lib64/qt6/qml/Pond/System/qmldir'
        module.chmod(0o666)
        with self.assertRaisesRegex(SystemExit, 'Insecure'):
            self.plan()

    def test_enable_failure_restores_previous_manager(self):
        error = dm.subprocess.CalledProcessError(1, ['systemctl'])
        with mock.patch.object(dm.subprocess, 'run', side_effect=[error, None]) as run:
            with self.assertRaises(dm.subprocess.CalledProcessError):
                dm.enable_sddm('plasmalogin.service')
        self.assertEqual(run.call_args_list[1].args[0],
                         ['systemctl', 'enable', '--force', 'plasmalogin.service'])

    def test_unknown_manager_blocks_install(self):
        link = self.root / 'etc/systemd/system/display-manager.service'
        link.unlink()
        link.symlink_to('/usr/lib/systemd/system/other.service')
        with self.assertRaisesRegex(SystemExit, 'Unsupported current display manager'):
            dm.install(self.source, self.root, dry_run=True, uid=self.uid)

    def test_dry_run_does_not_write(self):
        dm.install(self.source, self.root, dry_run=True, uid=self.uid)
        self.assertFalse((self.root / 'usr/local/share/pond-dm').exists())
        self.assertFalse((self.root / 'etc/sddm.conf.d/zz-pond-fedora.conf').exists())


if __name__ == '__main__':
    unittest.main()
