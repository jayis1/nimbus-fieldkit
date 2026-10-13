import importlib.util
import json
import os
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import shutil
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('dashboard_bundle', ROOT / 'scripts/package-native.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / 'native'
        self.install.mkdir()
        for name, source in package.SOURCES.items():
            output = self.install / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes((ROOT / source).read_bytes())
        self.proc = self.root / 'proc'; (self.proc / 'net').mkdir(parents=True)
        (self.proc / 'uptime').write_text('7200.00 1000.00\n')
        (self.proc / 'meminfo').write_text('MemTotal: 125496 kB\nMemFree: 16896 kB\nBuffers: 6948 kB\nCached: 47004 kB\n')
        (self.proc / 'net/route').write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\nwlan0 000BA8C0 00000000 0001 0 0 0 00FFFFFF 0 0 0\nwlan1 000A10AC 00000000 0001 0 0 0 00FFFFFF 0 0 0\nwlan1 00000000 FE0A10AC 0003 0 0 0 00000000 0 0 0\n')
        (self.proc / 'net/dev').write_text('Inter-| Receive | Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n wlan0: 0 0 0 0 0 0 0 0 155286 314 0 0 0 0 0 0\n wlan1: 230220 1639 0 0 0 0 0 0 549661 1169 0 0 0 0 0 0\n mon.wlan0: 39342599 111262 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n')
        (self.proc / 'net/tcp').write_text('  sl local_address rem_address st\n   0: 00000000:0017 00000000:0000 0A\n   1: 00000000:0050 00000000:0000 0A\n   2: 00000000:0016 00000000:0000 01\n')
        self.power = self.root / 'power'; self.power.mkdir()
        self.env = dict(os.environ, NIMBUS_PROC_DIR=str(self.proc), NIMBUS_POWER_DIR=str(self.power))

    def tearDown(self):
        self.temp.cleanup()

    def dashboard(self, *args, check=True):
        result = subprocess.run(['sh', str(self.install / 'nimbus-dashboard.sh'), *args], env=self.env, capture_output=True, text=True, timeout=10)
        if check: self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def setting(self, feature, value):
        subprocess.run(['sh', str(self.install / 'nimbus-settings.sh'), 'set', feature, value], env=self.env, check=True, capture_output=True)

    def state(self):
        return json.loads((self.install / 'dashboard/state.json').read_text())

    def test_snapshot_real_parsing_and_unknown_battery(self):
        self.dashboard('snapshot')
        data = self.state()
        self.assertEqual(data['schema'], 'nimbus-dashboard/v1')
        self.assertEqual(data['network']['gateway'], '172.16.10.254')
        self.assertEqual(data['network']['uplink'], 'wlan1')
        self.assertEqual(data['network']['subnets'][0]['address'], '192.168.11.0')
        self.assertFalse(data['network']['internet_verified'])
        self.assertEqual(data['memory']['total_bytes'], 125496*1024)
        self.assertEqual(data['memory']['reclaimable_estimate_bytes'], (16896+6948+47004)*1024)
        self.assertIsNone(data['battery']['capacity'])
        self.assertTrue(data['services']['telnet'])
        self.assertTrue(data['services']['http'])
        self.assertFalse(data['services']['ssh'])
        self.assertEqual(data['monitor_mode'], 'excluded')
        self.assertEqual(len(data['features']), 10)
        self.assertFalse(any(item['enabled'] for item in data['features']))

    def test_battery_requires_real_driver(self):
        supply=self.power/'battery'; supply.mkdir()
        (supply/'type').write_text('Battery\n'); (supply/'capacity').write_text('73\n'); (supply/'status').write_text('Discharging\n')
        self.dashboard('snapshot')
        self.assertEqual(self.state()['battery'], {'capacity':73,'status':'Discharging'})
        (supply/'capacity').write_text('not measured\n')
        self.dashboard('snapshot')
        self.assertIsNone(self.state()['battery']['capacity'])

    def test_flags_and_vault_inventory_no_symlink_read(self):
        self.setting('network_health','on'); self.setting('watchdog','on')
        vault=self.install/'vault'; vault.mkdir()
        (vault/'report.txt').write_text('data')
        (vault/'key.txt').symlink_to('/etc/passwd')
        self.dashboard('snapshot')
        data=self.state()
        self.assertTrue(next(item for item in data['features'] if item['id']=='watchdog')['enabled'])
        self.assertEqual(data['vault'], [{'name':'report.txt','bytes':4}])
        self.assertNotIn('root:', json.dumps(data))

    def test_import_validated_settings_no_overwrite(self):
        old=self.root/'old'; (old/'.settings').mkdir(parents=True)
        (old/'.settings/network_health').write_text('on\n')
        self.dashboard('import-settings',str(old))
        self.assertEqual((self.install/'.settings/network_health').read_text(),'on\n')
        self.assertNotEqual(self.dashboard('import-settings',str(old),check=False).returncode,0)

    def test_import_rejects_malformed_before_any_write(self):
        old=self.root/'old'; (old/'.settings').mkdir(parents=True)
        (old/'.settings/network_health').write_text('on; execute something\n')
        self.assertNotEqual(self.dashboard('import-settings',str(old),check=False).returncode,0)
        self.assertFalse((self.install/'.settings').exists())

    def test_snapshot_symlink_refused(self):
        target=self.root/'private'; target.write_text('do not overwrite')
        (self.install/'dashboard/state.json').symlink_to(target)
        self.assertNotEqual(self.dashboard('snapshot',check=False).returncode,0)
        self.assertEqual(target.read_text(),'do not overwrite')

    def test_separate_data_does_not_execute_mutable_scripts(self):
        data = self.root / 'data'; (data / 'dashboard').mkdir(parents=True)
        (data / '.settings').mkdir()
        (data / '.settings/network_health').write_text('on\n')
        marker = self.root / 'unsafe-execution'
        (data / 'nimbus-settings.sh').write_text(f'echo unsafe > "{marker}"\n')
        (data / 'dashboard/snapshot.awk').write_text('BEGIN { print "wrong encoder" }')
        self.env['NIMBUS_DATA_DIR'] = str(data)
        self.dashboard('snapshot')
        result = json.loads((data / 'dashboard/state.json').read_text())
        self.assertEqual(result['schema'], 'nimbus-dashboard/v1')
        self.assertTrue(next(f for f in result['features'] if f['id'] == 'network_health')['enabled'])
        self.assertFalse(marker.exists())
        self.assertFalse((self.install / 'dashboard/state.json').exists())

    def test_data_parent_symlink_refused(self):
        data = self.root / 'data'; (data / 'native/dashboard').mkdir(parents=True)
        (self.root / 'link').symlink_to(data, target_is_directory=True)
        self.env['NIMBUS_DATA_DIR'] = str(self.root / 'link/native')
        self.assertNotEqual(self.dashboard('snapshot', check=False).returncode, 0)
        self.assertFalse((data / 'native/dashboard/state.json').exists())

    def test_watch_requires_flags_and_is_bounded(self):
        self.assertNotEqual(self.dashboard('watch','1','5',check=False).returncode,0)
        self.setting('network_health','on'); self.setting('watchdog','on')
        self.dashboard('watch','1','5')
        self.assertEqual(self.state()['publisher'],'stopped')
        self.assertNotEqual(self.dashboard('watch','999999','5',check=False).returncode,0)

    def test_assets_dark_offline_and_not_a_web_shell(self):
        html=(ROOT/'fieldkit/index.html').read_text(); script=(ROOT/'fieldkit/dashboard.js').read_text()
        self.assertIn('data-theme="dark"',html)
        self.assertIn('dashboard.css',html); self.assertIn('dashboard.js',html)
        self.assertNotIn('https://',html)
        self.assertNotIn('innerHTML',script)
        self.assertNotIn('/api/execute',script)
        self.assertIn('Nothing executed',script)

    def test_shell_syntax(self):
        subprocess.run(['sh','-n',str(self.install/'nimbus-dashboard.sh')],check=True)

    @unittest.skipUnless(shutil.which('google-chrome') or shutil.which('chromium'), 'Chrome/Chromium is unavailable')
    def test_browser_dark_mode_features_commands_and_no_browser_writes(self):
        self.setting('network_health','on'); self.setting('watchdog','on')
        self.dashboard('snapshot')
        page=self.install/'dashboard/index.html'
        page.write_text(page.read_text().replace('</body>', '<script src="browser-test.js" defer></script></body>'))
        (self.install/'dashboard/browser-test.js').write_text('''
          (async () => {
            for(let i=0;i<80 && document.body.dataset.loaded!=='true';i++) await new Promise(resolve=>setTimeout(resolve,50));
            const checks=[];
            checks.push(document.body.dataset.loaded==='true');
            checks.push(document.getElementById('gateway').textContent==='172.16.10.254');
            checks.push(document.querySelectorAll('.feature-card').length===10);
            checks.push(document.documentElement.dataset.theme==='dark');
            document.getElementById('theme').click();
            checks.push(document.documentElement.dataset.theme==='light');
            document.getElementById('theme').click();
            document.querySelector('[data-view="features"]').click();
            const toggle=document.querySelector('[data-feature="network_health"] .switch');
            toggle.click();
            checks.push(document.getElementById('command-dialog').open);
            checks.push(document.getElementById('command-text').value.includes('settings set network_health off'));
            checks.push(toggle.getAttribute('aria-checked')==='true');
            document.getElementById('close-dialog').click();
            document.querySelector('[data-view="overview"]').click();
            document.body.dataset.browserTest=checks.every(Boolean) ? 'passed' : JSON.stringify(checks);
          })().catch(error=>{document.body.dataset.browserTest=error.message;});
        ''')
        class QuietHandler(SimpleHTTPRequestHandler):
            writes=0
            battery_queries=0
            def log_message(self,*args): pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                if self.path=='/NimbusAPI' and body==b'<?xml version="1.0"?><nimbus api="1.0" operation="getBatteryLevel"></nimbus>':
                    type(self).battery_queries+=1
                    self.send_response(200);self.end_headers()
                    self.wfile.write(b'<nimbus errcode="0"><level>100</level><status>full</status></nimbus>')
                    return
                type(self).writes+=1
                self.send_error(403)
        http=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(self.install)))
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            profile_root = '/tmp/opencode' if Path('/tmp/opencode').is_dir() else None
            with tempfile.TemporaryDirectory(dir=profile_root,prefix='nimbus-browser-') as profile:
                result=subprocess.run([shutil.which('google-chrome') or shutil.which('chromium'),'--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
                    '--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check',
                    '--user-data-dir='+profile,'--virtual-time-budget=5000','--dump-dom',
                    f'http://127.0.0.1:{http.server_port}/dashboard/index.html'],capture_output=True,text=True,timeout=35)
                self.assertEqual(result.returncode,0,result.stderr[-3000:])
                self.assertIn('data-browser-test="passed"',result.stdout)
                self.assertEqual(QuietHandler.writes,0)
                self.assertGreaterEqual(QuietHandler.battery_queries,1)
        finally:
            http.shutdown();http.server_close();thread.join()
