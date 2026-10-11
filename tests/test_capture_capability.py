from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'device/capture-capability-preflight.sh'


class CaptureCapabilityTests(unittest.TestCase):
    def run_fixture(self, folder, exported=False, watchdog=False, swap=False):
        base = Path(folder)
        proc = base / 'proc'; proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 262144 kB\nMemFree: 8192 kB\n')
        (proc / 'mounts').write_text('/dev/root / ext3 rw 0 0\ntmpfs /tmp tmpfs rw 0 0\n')
        (proc / 'kallsyms').write_text('c0000123 T freeze_super\nc0000456 T thaw_super\nc0000789 T unrelated_symbol\n')
        (proc / 'modules').write_text('g_file_storage 1 0 - Live 0\n' if exported else '')
        (proc / 'swaps').write_text('Filename Type Size Used Priority\n' +
                                   ('/opt/qsi/fwpool/private-swap-name file 151712 3492 -1\n' if swap else ''))
        if swap:
            with (proc / 'mounts').open('a') as out:
                out.write('/dev/mmcblk0p3 /opt/qsi/fwpool ext3 rw 0 0\n')
        if watchdog:
            fds = proc / '42/fd'; fds.mkdir(parents=True)
            (fds / '3').symlink_to(base / 'dev/watchdog')
            (fds / '4').symlink_to('/private/credential-filename')
        tool = base / 'sbin/fsfreeze'; tool.parent.mkdir()
        tool.write_text('#!/bin/sh\necho UNSAFE-TOOL-EXECUTED\nexit 99\n'); tool.chmod(0o700)
        script = SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]', ':')
        script = script.replace('uname -r', 'printf fixture-kernel')
        script = script.replace('/proc/', str(proc) + '/').replace('/sys/', str(base / 'sys') + '/')
        script = script.replace('/dev/', str(base / 'dev') + '/')
        script = script.replace(str(base / 'dev/null'), '/dev/null')
        script = script.replace('/sbin/fsfreeze', str(tool))
        script = script.replace('/usr' + str(tool), str(base / 'absent-tool'))
        path = base / 'inventory.sh'; path.write_text(script)
        before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
        result = subprocess.run(['sh', str(path)], capture_output=True, text=True, timeout=10)
        after = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        return result

    def test_inventory_does_not_execute_freeze_or_expose_symbol_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_fixture(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NO FREEZE OR RECOVERY AUTHORIZATION', result.stdout)
            self.assertIn('freeze_super\nthaw_super', result.stdout)
            self.assertNotIn('c0000123', result.stdout)
            self.assertNotIn('UNSAFE-TOOL-EXECUTED', result.stdout)
            self.assertIn('does not prove it inactive', result.stdout)

    def test_active_usb_export_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_fixture(folder, exported=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ACTIVE', result.stdout)

    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(SCRIPT)], check=True)

    def test_watchdog_links_and_swap_backing_without_private_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_fixture(folder, watchdog=True, swap=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('pid=42 fd=3 standard-watchdog-link', result.stdout)
            self.assertIn('Observed standard watchdog fd links: 1', result.stdout)
            self.assertIn('backing=/dev/mmcblk0p3', result.stdout)
            self.assertNotIn('private-swap-name', result.stdout)
            self.assertNotIn('credential-filename', result.stdout)
            self.assertIn('zero links does NOT prove watchdog inactive', result.stdout)
