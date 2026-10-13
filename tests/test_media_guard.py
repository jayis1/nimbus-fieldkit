import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('media_guard_bundle',ROOT/'scripts/package-native.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


class MediaGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.proc=self.root/'proc';self.proc.mkdir()
        self.media=self.root/'storage';self.media.mkdir()
        self.sd=self.root/'sdcard';self.sd.mkdir()
        self.native=self.media/'native';self.native.mkdir()
        for name,source in package.SOURCES.items():
            path=self.native/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/source).read_bytes())
        guard=self.native/'nimbus-media-guard.sh'
        guard.write_text(guard.read_text().replace('/mnt/storage',str(self.media)).replace('/mnt/sdcard',str(self.sd)))
        self.env=dict(os.environ,NIMBUS_PROC_DIR=str(self.proc))
        (self.proc/'modules').write_text('')
        (self.proc/'mounts').write_text(f'/dev/mmcblk0p4 {self.media} texfat rw,relatime 0 0\n')

    def guard(self,path=None,mode='check-write'):
        return subprocess.run(['sh',str(self.native/'nimbus-media-guard.sh'),mode,str(path or self.native)],env=self.env,capture_output=True,text=True,timeout=5)

    def test_expected_local_rw_and_read_only_reads(self):
        self.assertEqual(self.guard().returncode,0)
        (self.proc/'mounts').write_text(f'/dev/mmcblk0p4 {self.media} texfat ro,relatime 0 0\n')
        self.assertNotEqual(self.guard().returncode,0)
        self.assertEqual(self.guard(mode='check-read').returncode,0)

    def test_export_missing_and_malformed_inventory_refuse(self):
        for content in ('g_file_storage 1 0 - Live 0\n','g_mass_storage 1 0 - Live 0\n','g_multi 1 0 - Live 0\n','g_custom 1 0 - Live 0\n','broken inventory\n'):
            with self.subTest(content=content):
                (self.proc/'modules').write_text(content)
                self.assertNotEqual(self.guard().returncode,0)
        (self.proc/'modules').unlink()
        self.assertNotEqual(self.guard().returncode,0)

    def test_absent_readonly_wrong_source_duplicate_and_nested_mounts_refuse(self):
        rows=('',f'/dev/mmcblk0p4 {self.media} texfat ro 0 0\n',
              f'/dev/mmcblk0p3 {self.media} texfat rw 0 0\n',
              f'/dev/mmcblk0p4 {self.media} tmpfs rw 0 0\n',
              f'/dev/mmcblk0p4 {self.media} texfat rw,ro 0 0\n',
              f'/dev/mmcblk0p4 {self.media} texfat rw 0 0\n'*2,
              f'/dev/mmcblk0p4 {self.media} texfat rw 0 0\nnone {self.native} tmpfs rw 0 0\n')
        for row in rows:
            with self.subTest(row=row):
                (self.proc/'mounts').write_text(row)
                self.assertNotEqual(self.guard().returncode,0)

    def test_alias_noncanonical_and_symlink_paths_refuse(self):
        for path in ('/var/ftp/storage/test','/storage/test','relative',str(self.native)+'/../x',str(self.native)+'//x'):
            with self.subTest(path=path):self.assertNotEqual(self.guard(path).returncode,0)
        link=self.native/'linked';link.symlink_to(self.root)
        self.assertNotEqual(self.guard(link/'new').returncode,0)
        self.assertNotEqual(self.guard(str(link)+'/').returncode,0)
        alias=self.root/'alias';alias.mkdir()
        with (self.proc/'mounts').open('a') as stream:stream.write(f'/dev/mmcblk0p4 {alias} texfat rw 0 0\n')
        self.assertNotEqual(self.guard(alias/'new').returncode,0)

    def test_sd_requires_exact_source_and_supported_mount(self):
        (self.proc/'mounts').write_text(f'/dev/mmcblk1p1 {self.sd} texfat rw 0 0\n')
        self.assertEqual(self.guard(self.sd/'new').returncode,0)
        (self.proc/'mounts').write_text(f'/dev/mmcblk0p4 {self.sd} texfat rw 0 0\n')
        self.assertNotEqual(self.guard(self.sd/'new').returncode,0)

    def test_proc_mounts_kernel_style_symlink_supported(self):
        mounts=self.proc/'mounts';mounts.rename(self.proc/'real-mounts');mounts.symlink_to('real-mounts')
        self.assertEqual(self.guard().returncode,0)

    def test_settings_and_publisher_refuse_before_writing_on_export(self):
        (self.proc/'modules').write_text('g_file_storage 1 0 - Live 0\n')
        settings=subprocess.run(['sh',str(self.native/'nimbus-settings.sh'),'set','network_health','on'],env=self.env,capture_output=True,timeout=5)
        self.assertNotEqual(settings.returncode,0);self.assertFalse((self.native/'.settings').exists())
        result=subprocess.run(['sh',str(self.native/'nimbus-dashboard.sh'),'snapshot'],env=self.env,capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.native/'dashboard/.publish-lock').exists());self.assertFalse((self.native/'dashboard/state.json').exists())

    def test_sync_refuses_exported_destination_and_readonly_source_is_allowed(self):
        (self.native/'.settings').mkdir();(self.native/'.settings/file_sync').write_text('on\n')
        source=self.root/'report.txt';source.write_bytes(b'reviewed fixture')
        destination=self.native/'vault';destination.mkdir()
        (self.proc/'modules').write_text('g_file_storage 1 0 - Live 0\n')
        result=subprocess.run(['sh',str(self.native/'nimbus-settings.sh'),'run','file_sync',str(source),str(destination)],env=self.env,capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertFalse((destination/source.name).exists())
        (self.proc/'modules').write_text('')
        (self.proc/'mounts').write_text(f'/dev/mmcblk0p4 {self.media} texfat rw 0 0\n/dev/mmcblk1p1 {self.sd} texfat ro 0 0\n')
        source=self.sd/'report.txt';source.write_bytes(b'reviewed fixture')
        result=subprocess.run(['sh',str(self.native/'nimbus-settings.sh'),'run','file_sync',str(source),str(destination)],env=self.env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual((destination/source.name).read_bytes(),source.read_bytes())

    def test_ownership_loss_before_snapshot_commit_preserves_original_and_evidence(self):
        (self.proc/'net').mkdir()
        fixtures={'uptime':'12.00 1.00\n','meminfo':'MemTotal: 1024 kB\nMemFree: 512 kB\n',
                  'net/route':'Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n',
                  'net/dev':'Inter-| Receive | Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n',
                  'net/tcp':'sl local_address rem_address st\n'}
        for name,content in fixtures.items():(self.proc/name).write_text(content)
        state=self.native/'dashboard/state.json';state.write_bytes(b'previous snapshot; preserve')
        encoder=self.native/'dashboard/snapshot.awk'
        # The fixture injects a USB-state transition during encoding, not an
        # actual module/device change. Publication must be refused afterward.
        modules=str(self.proc/'modules')
        encoder.write_text('BEGIN {print "g_file_storage 1 0 - Live 0" > "'+modules+'"; close("'+modules+'")}\n'+encoder.read_text())
        result=subprocess.run(['sh',str(self.native/'nimbus-dashboard.sh'),'snapshot'],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(state.read_bytes(),b'previous snapshot; preserve')
        lock=self.native/'dashboard/.publish-lock'
        self.assertTrue(lock.is_dir());self.assertTrue((lock/'state.json').is_file())

    def test_settings_ownership_loss_preserves_old_flag_and_partial_evidence(self):
        state=self.native/'.settings';state.mkdir();(state/'network_health').write_text('off\n')
        guard=self.native/'nimbus-media-guard.sh'
        real=self.native/'real-media-guard.sh';guard.rename(real)
        count=self.root/'calls'
        guard.write_text(f'''#!/bin/sh
if [ -e "{count}" ]; then printf 'g_file_storage 1 0 - Live 0\\n' > "{self.proc/'modules'}";
else printf 'first\\n' > "{count}"; fi
exec sh "{real}" "$@"
''')
        result=subprocess.run(['sh',str(self.native/'nimbus-settings.sh'),'set','network_health','on'],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((state/'network_health').read_text(),'off\n')
        self.assertTrue((state/'.write-lock').is_dir())
        self.assertEqual(len(list(state.glob('.toggle.*'))),1)

    def test_syntax_and_no_mount_service_or_usb_actions(self):
        path=ROOT/'device/nimbus-media-guard.sh'
        subprocess.run(['sh','-n',str(path)],check=True)
        text=path.read_text()
        for forbidden in ('mkdir ','mount -','umount ','modprobe ','rmmod ','setUseServices','rm -'):
            self.assertNotIn(forbidden,text)
