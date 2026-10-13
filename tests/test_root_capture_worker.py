import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_root_restoration_trial as restoration

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_worker_generator', ROOT / 'scripts/prepare-root-capture-worker.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
TOKEN = 'a' * 64
DATA = bytes(range(256)) * 1024
DIGEST = hashlib.sha256(DATA).hexdigest()


class GeneratorTests(unittest.TestCase):
    def test_cleanup_protection_does_not_leak_ignored_term_to_services(self):
        text = generator.generate((ROOT/'device/root-restoration-trial.sh').read_text())
        self.assertIn("trap '' HUP INT TERM", text)
        self.assertIn('(trap - HUP INT TERM; exec sh "$service" start)', text)
        self.assertIn('(trap - HUP INT TERM; exec nohup setsid sh "$launcher")', text)
        with tempfile.TemporaryDirectory() as temporary:
            service = Path(temporary)/'signal-check.sh'
            service.write_text('"'+sys.executable+'" -c "import signal; assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL"\n')
            result = subprocess.run(['sh', '-c', 'trap "" HUP INT TERM; (trap - HUP INT TERM; exec sh "$1") & wait "$!"',
                                     'fixture', str(service)], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_strict_template_layout_and_no_launch_mode(self):
        text = generator.generate((ROOT / 'device/root-restoration-trial.sh').read_text())
        self.assertNotIn('mode" = --start', text)
        self.assertIn('drain_capture && no_raw_readers && restore_rw', text)
        self.assertIn('exec 3>&1', text)
        self.assertIn('exec 1>&2', text)
        result = subprocess.run(['sh', '-n'], input=text.encode(), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(ValueError):
            generator.generate('unreviewed template')

    def test_pinned_component_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / 'component'
            component.mkdir()
            (component / 'root-capture-stream.arm').write_bytes(b'not a pinned binary')
            with self.assertRaises(ValueError):
                generator.prepare(component, root / 'new')
            self.assertFalse((root / 'new').exists())
        actual = ROOT / 'build/nimbus-root-capture-stream-v3'
        if actual.exists():
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'coordinator'
                manifest = generator.prepare(actual, output)
                self.assertFalse(manifest['installable'])
                with self.assertRaises(FileExistsError):
                    generator.prepare(actual, output)


@unittest.skipUnless(shutil.which('gcc') and Path('/usr/bin/sha256sum').is_file(), 'Host C compiler/hasher unavailable')
class CaptureWorkerTests(unittest.TestCase):
    def fixture(self, base, **kwargs):
        stage, proc, database = restoration.RootRestorationTrialTests().fixture(base, **kwargs)
        binary = stage / 'streamer'
        subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DNIMBUS_CAPTURE_FIXTURE', str(ROOT / 'device/root-capture-stream.c'),
                        '-o', str(binary)], check=True, capture_output=True)
        binary.chmod(0o700)
        (base / 'dev').mkdir()
        (base / 'dev/mmcblk0p2').write_bytes(DATA)
        block = base / 'sys/class/block/mmcblk0p2'
        (block / 'start').write_text('38912\n'); (block / 'size').write_text('512\n')
        busybox = base / 'bin/busybox'
        busybox.write_bytes(b'fixture dependency, never executed by shell checks')
        busybox.chmod(0o700)
        hasher=base/'usr/bin/sha256sum'
        hasher.parent.mkdir(parents=True,exist_ok=True)
        hasher.write_bytes(b'fixture standalone hasher metadata, never executed')
        hasher.chmod(0o755)
        text = generator.generate((ROOT / 'device/root-restoration-trial.sh').read_text())
        inputs = {
            '1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c': base / 'root/nimbus-ssh-test/dropbearmulti-bound',
            '173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41': base / 'root/nimbus-ssh-test/startup-v1/start-ssh.sh',
            'b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd': base / 'nimbus/nimbus',
            '2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3': base / 'etc/rc.d/init.d/service/S20nimbus',
            '5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be': base / 'bin/mount',
            'aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c': busybox,
            'c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2': hasher,
            generator.STREAM_HASH: binary,
            '6a32518bd0e5f024a766a8cfb3f722dc4752b952b4ce629ed27fcc8bca4293f5': base / 'opt/qsi/config/nimbus.conf',
            '970a00795c0464a7e97b44d6b50d5bd9dbe6f851d51c7408b55cd058e3c93664': base / 'opt/qsi/config/develop.conf',
            '16bcf3ec02fc8a660256bfa37674d6dfd5ef786345d7c2ff624cf1c2b030e136': base / 'opt/qsi/config/platform_functions',
        }
        for old, path in inputs.items():
            text = text.replace(old, hashlib.sha256(path.read_bytes()).hexdigest())
        text = text.replace('[ "$(id -u)" = 0 ]', ':')
        text = text.replace("stat -c '%u:%g:%a'", "stat -c '0:0:%a'").replace("stat -c '%u:%g'", "stat -c '0:0'")
        text = text.replace("stat -c '%u:%g:%a:%s'", "stat -c '0:0:%a:%s'").replace('0:0:755:116878',f'0:0:755:{hasher.stat().st_size}')
        text = text.replace("root_dev=$(stat -c '%d' /)", "root_dev=$(stat -c '%d' '"+str(base)+"')")
        text = text.replace(generator.STAGE, '/tmp/nimbus-ssh-handover-trial-v2')
        # One-pass replacement cannot recursively rewrite /tmp inside prior paths.
        names = ('/proc/', '/sys/', '/root/', '/tmp/', '/nimbus/', '/bin/mount', '/bin/busybox', '/usr/bin/sha256sum', '/etc/', '/opt/')
        pattern = '|'.join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        text = re.sub(pattern, lambda match: str(base / match[0].strip('/')) + ('/' if match[0].endswith('/') else ''), text)
        for name in ('/tmp', '/root', '/bin', '/etc', '/opt', '/nimbus'):
            text = text.replace(' '+name+' ', ' "'+str(base/name.strip('/'))+'" ').replace(' '+name+';', ' "'+str(base/name.strip('/'))+'";')
        text = text.replace('[ -b /dev/mmcblk0p2 ]', '[ -f '+str(base / 'dev/mmcblk0p2')+' ]')
        text = text.replace(')" = 524288 ]', ')" = 512 ]')
        text = text.replace('"$capture_session" <&0 >&3 4>&4 &', '"$capture_session" "'+str(base)+'" <&0 >&3 4>&4 &')
        # For the real test-owned native helper only, use actual /proc identity.
        # The simulated old/vendor services retain synthetic /proc and signal stubs.
        text = text.replace('capture_stamp=$(start_time "$capture_pid" 2>/dev/null || :)',
                            'capture_stamp=$(sed \'s/.*) //\' "/proc/$capture_pid/stat" | awk \'{print $20}\')')
        start = text.index('capture_child_ok() {\n')
        end = text.index('child_drain_ok() {\n', start)
        text = text[:start] + '''capture_child_ok() {
    [ -n "$capture_pid" ] && [ -n "$capture_stamp" ] &&
    [ "$(readlink "/proc/$capture_pid/exe")" = "$capture_binary" ] &&
    [ "$(sed 's/.*) //' "/proc/$capture_pid/stat" | awk '{print $20}')" = "$capture_stamp" ] &&
    printf '%s  %s\\n' "$capture_hash" "/proc/$capture_pid/exe" | sha256sum -c - >/dev/null
}
''' + text[end:]
        identity = (stage/'identity.sh').read_text().replace('kill() {', 'fixture_service_kill() {')
        identity += '''\nkill() {
    case "$2" in 100|300) fixture_service_kill "$@";;
        *) [ "$2" = "${capture_pid-}" ] && capture_child_ok && /bin/kill "$@";;
    esac
}\n'''
        (stage/'identity.sh').write_text(identity)
        worker = stage / 'worker.sh'
        worker.write_text(text)
        (stage / 'started').write_text(TOKEN+'\n')
        for name in ('worker.sh', 'identity.sh', 'started', 'worker.log'):
            (stage / name).chmod(0o600)
        (stage / 'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('worker.sh', 'identity.sh', 'streamer')))
        return stage, proc, database

    def run_case(self, mode='--worker', ack=None, **kwargs):
        cache = Path.home() / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-fixture-', dir=cache) as temporary:
            base = Path(temporary)
            stage, proc, database = self.fixture(base, **kwargs)
            if mode == '--check':
                (stage/'started').unlink(); (stage/'worker.log').unlink()
            old_data = database.read_bytes()
            args = ['sh', str(stage/'worker.sh'), mode] + ([TOKEN] if mode == '--worker' else [])
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            result = subprocess.run(args, input=ack if ack is not None else f'NIMBUS-HOST-VERIFIED {TOKEN} {DIGEST}\n'.encode(),
                                    capture_output=True, env=env, timeout=15)
            self.assertEqual(database.read_bytes(), old_data)
            self.assertTrue((proc/'200').exists())
            logs = {name: (stage/name).read_text() if (stage/name).exists() else '' for name in ('signals', 'starts', 'mounts', 'RESULT')}
            return result, logs

    def test_check_only_never_stops_mounts_reads_or_starts(self):
        result, logs = self.run_case(mode='--check')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(logs, {name: '' for name in logs})
        self.assertNotIn(b'NIMBUS-ROOT-BEGIN', result.stdout)

    def test_success_with_real_native_stream_and_real_inventory_fixture(self):
        result, logs = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(logs['signals'], 'TERM 100\nTERM 300\n')
        self.assertEqual(logs['starts'], 'vendor\nssh\n')
        self.assertEqual(logs['RESULT'], TOKEN+' PASS\n')
        self.assertEqual(logs['mounts'].count('-n -i -r'), 1)
        self.assertEqual(logs['mounts'].count('-n -i -w'), 1)
        self.assertEqual(result.stdout,
                         f'NIMBUS-ROOT-BEGIN {TOKEN} {len(DATA)} 179:2 ro\n'.encode() + DATA +
                         f'NIMBUS-ROOT-END {TOKEN} {DIGEST}\n'.encode() +
                         f'NIMBUS-ROOT-RESULT {TOKEN} ro-until-ack rw-restored ssh-restored vendor-restored\n'.encode())

    def test_missing_or_wrong_ack_restores_but_never_reports_success(self):
        for ack in (b'', b'invalid ack\n'):
            result, logs = self.run_case(ack=ack)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(logs['RESULT'], TOKEN+' FAIL\n')
            self.assertEqual(logs['starts'], 'vendor\nssh\n')
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', result.stdout)

    def test_stop_refusal_does_not_progress_to_raw_capture(self):
        for kwargs in ({'old_stop': False}, {'vendor_stop': False}):
            result, logs = self.run_case(**kwargs)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(logs['mounts'], '')
            self.assertNotIn(b'NIMBUS-ROOT-BEGIN', result.stdout)

    def test_ro_failure_and_rw_failure_never_repeat_or_publish_success(self):
        for kwargs in ({'ro_works': False}, {'rw_works': False}, {'wrong_ro_options': True}):
            result, logs = self.run_case(**kwargs)
            self.assertNotEqual(result.returncode, 0)
            self.assertLessEqual(logs['mounts'].count('-n -i -r'), 1)
            self.assertLessEqual(logs['mounts'].count('-n -i -w'), 1)
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', result.stdout)

    def test_vendor_restore_failure_does_not_suppress_ssh_restore(self):
        result, logs = self.run_case(vendor_restart=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(logs['starts'], 'vendor\nssh\n')
        self.assertEqual(logs['RESULT'], TOKEN+' FAIL\n')
        self.assertNotIn(b'NIMBUS-ROOT-RESULT', result.stdout)

    def test_coordinator_term_drains_native_ack_wait_before_rw(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-cancel-', dir=Path.home()/'.cache') as temporary:
            stage, proc, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                process.stdout.readline(); process.stdout.read(len(DATA)); process.stdout.readline()
                process.send_signal(signal.SIGTERM)
                # Keep control stdin open while coordinator cancels its own verified child.
                self.assertNotEqual(process.wait(timeout=10), 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', process.stdout.read())
            self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
            self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
            self.assertEqual((stage/'mounts').read_text().count('-n -i -w'), 1)
            self.assertIn(' rw,', (proc/'mounts').read_text())

    def test_abnormal_helper_death_blocks_rw_and_service_starts(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-abnormal-', dir=Path.home()/'.cache') as temporary:
            stage, proc, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                process.stdout.readline(); process.stdout.read(len(DATA)); process.stdout.readline()
                # Only our freshly checked direct test child, after its hasher exited.
                children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
                native = [int(pid) for pid in children if Path(f'/proc/{pid}/exe').resolve() == stage/'streamer']
                self.assertEqual(len(native), 1)
                os.kill(native[0], signal.SIGKILL)
                self.assertNotEqual(process.wait(timeout=10), 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', process.stdout.read())
            self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
            self.assertFalse((stage/'starts').exists())
            self.assertNotIn('-n -i -w', (stage/'mounts').read_text())
            self.assertIn(' ro,', (proc/'mounts').read_text())

    def test_lost_fallback_after_stream_blocks_restoration(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-fallback-', dir=Path.home()/'.cache') as temporary:
            stage, proc, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                process.stdout.readline(); process.stdout.read(len(DATA)); process.stdout.readline()
                # Remove only the synthetic fallback's identity, never a real listener.
                (proc/'200/stat').write_text('invalid identity\n')
                stdout, _ = process.communicate(f'NIMBUS-HOST-VERIFIED {TOKEN} {DIGEST}\n'.encode(), timeout=10)
                self.assertNotEqual(process.returncode, 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', stdout)
            self.assertFalse((stage/'starts').exists())
            self.assertNotIn('-n -i -w', (stage/'mounts').read_text())
            self.assertIn(' ro,', (proc/'mounts').read_text())

    def test_missing_child_drain_evidence_blocks_rw_even_with_valid_ack(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-drain-', dir=Path.home()/'.cache') as temporary:
            stage, proc, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                process.stdout.readline(); process.stdout.read(len(DATA)); process.stdout.readline()
                # The native helper owns an fd to this original inode. Removing
                # its fixture name must not be interpreted as a cleanup report.
                (stage/'CHILD-DRAIN').unlink()
                stdout, _ = process.communicate(f'NIMBUS-HOST-VERIFIED {TOKEN} {DIGEST}\n'.encode(), timeout=10)
                self.assertNotEqual(process.returncode, 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', stdout)
            self.assertFalse((stage/'starts').exists())
            self.assertNotIn('-n -i -w', (stage/'mounts').read_text())
            self.assertIn(' ro,', (proc/'mounts').read_text())

    def test_private_result_commit_failure_withholds_success(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-evidence-', dir=Path.home()/'.cache') as temporary:
            stage, _, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                process.stdout.readline(); process.stdout.read(len(DATA)); process.stdout.readline()
                (stage/'RESULT').mkdir()  # Race/failure injection after preflight.
                stdout, stderr = process.communicate(f'NIMBUS-HOST-VERIFIED {TOKEN} {DIGEST}\n'.encode(), timeout=10)
                self.assertNotEqual(process.returncode, 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', stdout)
                self.assertIn(b'Private result recording failed', stderr)
            self.assertTrue((stage/'RESULT').is_dir())

    def test_real_coordinator_streamer_and_host_receiver_round_trip(self):
        spec = importlib.util.spec_from_file_location('worker_receiver', ROOT/'scripts/receive-root-capture.py')
        receiver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(receiver)
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-receiver-', dir=Path.home()/'.cache') as temporary:
            base = Path(temporary)
            stage, _, _ = self.fixture(base)
            private = base/'private'
            with patch.object(receiver, 'PRIVATE', private), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(private/'round-trip')
                env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
                with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                    manifest = receiver.receive(process.stdout, process.stdin, output, TOKEN)
                    self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())
                self.assertEqual((output/'rootfs.bin').read_bytes(), DATA)
                self.assertEqual(manifest['sha256'], DIGEST)
                self.assertFalse(manifest['filesystem_consistency_verified'])
                self.assertFalse(manifest['flash_authorized'])

    def test_output_disconnect_restores_without_success(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-disconnect-', dir=Path.home()/'.cache') as temporary:
            stage, _, _ = self.fixture(Path(temporary))
            env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
            with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
                self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN'))
                process.stdout.close()
                self.assertNotEqual(process.wait(timeout=10), 0)
            self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
            self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
            self.assertEqual((stage/'mounts').read_text().count('-n -i -w'), 1)

    def test_transport_round_trip_checks_exit_before_host_receipt(self):
        spec = importlib.util.spec_from_file_location('worker_transport', ROOT/'scripts/root-capture-transport.py')
        transport = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(transport)
        with tempfile.TemporaryDirectory(prefix='nimbus-coordinator-transport-', dir=Path.home()/'.cache') as temporary:
            base = Path(temporary)
            stage, _, _ = self.fixture(base)
            receiver = transport.load_receiver()
            with patch.object(receiver, 'PRIVATE', base/'private'), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(receiver.PRIVATE/'attempt')
                env = dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')
                with subprocess.Popen(['sh', str(stage/'worker.sh'), '--worker', TOKEN], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0) as process:
                    manifest = transport.receive_process(process, output, TOKEN, seconds=15, receiver=receiver)
                    self.assertEqual(process.returncode, 0)
                self.assertEqual((output/'rootfs.bin').read_bytes(), DATA)
                self.assertTrue((output/'CAPTURE-MANIFEST.json').exists())
                self.assertIn(b'Restoration observed', (output/'TRANSPORT-STDERR.log').read_bytes())
                self.assertFalse(manifest['filesystem_consistency_verified'])
