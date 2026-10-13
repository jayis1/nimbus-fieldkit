import importlib.util
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tarfile
import tempfile
import threading
import shutil
import unittest

ROOT=Path(__file__).resolve().parents[1]


class DashboardArchitectureTests(unittest.TestCase):
    def test_current_roles_replace_single_usb_worker(self):
        html=(ROOT/'fieldkit/index.html').read_text()
        js=(ROOT/'fieldkit/dashboard.js').read_text()
        for text in ('Pi A','Pi B','pinned Wi-Fi SSH','not an SSH jump host','Handheld direct-USB/accessory workflows are retired'):
            self.assertIn(text,html)
        for obsolete in ('Independent USB worker','existing key-pinned USB SSH client','<dt>USB address</dt>'):
            self.assertNotIn(obsolete,html)
        self.assertNotIn('existing pinned Pi USB client',js)
        self.assertIn('not automatically on B',js)

    def test_missing_telemetry_clears_stale_measurements_and_flags(self):
        js=(ROOT/'fieldkit/dashboard.js').read_text()
        self.assertIn('Device telemetry unavailable (HTTP ',js)
        self.assertIn('data=null; history=[]; lastTraffic=null',js)
        self.assertIn("document.body.dataset.scope='unavailable'",js)
        self.assertIn("text('enabled-caption','No current native settings')",js)
        self.assertIn('renderFeatures(); renderBattery();',js)
        self.assertIn('notice(error.message+storageReason,true)',js)
        self.assertIn('operation="getUseServices"',js)
        self.assertIn('do not mount it while a USB host owns it',js)
        self.assertNotIn('No native snapshot yet.',js)

    def test_overview_hash_opens_existing_fieldkit_surface(self):
        js=(ROOT/'device/unified/bridge.js').read_text()
        self.assertIn('const requestedView = location.hash.slice(1)',js)
        self.assertIn('pendingView = requestedView;',js)
        self.assertIn('nav.click();',js)

    def test_generated_overlay_contains_updated_roles_and_no_fake_telemetry(self):
        stock=ROOT/'numbus-backup/stock-web.tar'
        if not stock.exists():self.skipTest('Stock input unavailable')
        spec=importlib.util.spec_from_file_location('ab_unified_builder',ROOT/'scripts/build-unified-dashboard.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'overlay.tar';builder.build(stock,output)
            with tarfile.open(output) as archive:
                html=archive.extractfile('fieldkit-v05/toolkit.html').read().decode()
                self.assertIn('Pi A',html);self.assertIn('Pi B',html)
                self.assertNotIn('Independent USB worker',html)
                self.assertFalse(any(name.endswith('state.json') for name in archive.getnames()))

    def test_metadata_preflight_syntax_and_refusal(self):
        source=ROOT/'device/dashboard-ui-preflight.sh'
        subprocess.run(['sh','-n',str(source)],check=True,capture_output=True)
        result=subprocess.run(['sh',str(source),'--start'],capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,b'')
        text=source.read_text()
        for forbidden in ('mkdir ','chmod ','mount -','nimbus-dashboard.sh snapshot','nimbus-dashboard.sh watch','rm -','cp '):
            self.assertNotIn(forbidden,text)

    def test_homepage_battery_uses_read_only_vendor_query(self):
        js=(ROOT/'device/unified/battery.js').read_text()
        self.assertIn('nimbus-home-battery',js)
        self.assertIn('operation="getBatteryLevel"',js)
        self.assertIn('Battery: Unknown',js)
        self.assertIn("charge:'Charging'",js)
        for forbidden in ('setUseServices','setSSID','AdminLogin','upgradeFirmware'):
            self.assertNotIn(forbidden,js)
        self.assertIn('capacity:null',js)

    def test_generated_overlay_includes_battery_asset(self):
        stock=ROOT/'numbus-backup/stock-web.tar'
        if not stock.exists():self.skipTest('Stock input unavailable')
        spec=importlib.util.spec_from_file_location('battery_unified_builder',ROOT/'scripts/build-unified-dashboard.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'overlay.tar';builder.build(stock,output)
            with tarfile.open(output) as archive:
                self.assertIn('fieldkit-v05/battery.js',archive.getnames())
                self.assertIn(b"batteryScript.src = prefix + 'battery.js'",archive.extractfile('fieldkit-v05/bridge.js').read())

    @unittest.skipUnless(shutil.which('chromium'),'Chromium unavailable')
    def test_standalone_and_shadow_battery_without_snapshot_or_header(self):
        spec=importlib.util.spec_from_file_location('battery_integration_builder',ROOT/'scripts/build-unified-dashboard.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        for shadow in (False,True):
            with self.subTest(shadow=shadow),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);assets=root/'dashboard';assets.mkdir()
                if shadow:
                    markup,css,script=builder.toolkit_assets()
                    bootstrap="const host=document.createElement('div');document.body.append(host);window.NIMBUS_UNIFIED_SURFACE=host.attachShadow({mode:'open'});window.NIMBUS_UNIFIED_SURFACE.innerHTML="+__import__('json').dumps(markup)+";"
                    page='<html><head></head><body><script>'+bootstrap+'</script><script src="dashboard.js"></script></body></html>'
                else:
                    page=(ROOT/'fieldkit/index.html').read_text()
                    script=(ROOT/'fieldkit/dashboard.js').read_text()
                (assets/'index.html').write_text(page.replace('</body>','<script src="test.js"></script></body>'))
                (assets/'dashboard.js').write_text(script)
                (assets/'battery.js').write_bytes((ROOT/'device/unified/battery.js').read_bytes())
                (assets/'test.js').write_text('''
                (async()=>{
                  const surface=window.NIMBUS_UNIFIED_SURFACE || document;
                  const wait=()=>new Promise(resolve=>setTimeout(resolve,50));
                  for(let i=0;i<100 && !surface.getElementById('battery').textContent.includes('100%');i++)await wait();
                  const checks=[surface.getElementById('battery').textContent==='100% / Full · device API',
                    !document.getElementById('nimbus-global-controls'),
                    (window.NIMBUS_UNIFIED_SURFACE?.host || document.body).dataset.scope==='unavailable'];
                  // Independent refresh works even when snapshot publication fails.
                  window.dispatchEvent(new CustomEvent('nimbus-battery-refresh-request'));
                  await wait();await wait();
                  checks.push(surface.getElementById('battery').textContent==='100% / Full · device API');
                  document.body.dataset.test=checks.every(Boolean)?'PASS':'FAIL';
                  document.body.dataset.checks=checks.map(Number).join('');
                })().catch(error=>{document.body.dataset.test='ERROR';document.body.dataset.error=error.message});
                ''')
                operations=[]
                class Handler(SimpleHTTPRequestHandler):
                    def log_message(self,*args):pass
                    def do_POST(self):
                        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                        operations.append(body)
                        if b'operation="getBatteryLevel"' in body:
                            response=b'<nimbus errcode="0"><level>100</level><status>full</status></nimbus>'
                        elif b'operation="getUseServices"' in body:
                            response=b'<nimbus errcode="0"><MSCMode>true</MSCMode></nimbus>'
                        else:
                            self.send_error(403);return
                        self.send_response(200);self.send_header('Content-Type','text/xml');self.end_headers();self.wfile.write(response)
                server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(root)))
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    result=subprocess.run(['chromium','--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
                      '--disable-background-networking','--no-first-run','--user-data-dir='+str(root/'chrome'),
                      '--virtual-time-budget=7000','--dump-dom',f'http://127.0.0.1:{server.server_port}/dashboard/index.html'],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr[-2000:])
                    self.assertIn('data-test="PASS"',result.stdout,result.stdout[-3000:])
                    self.assertTrue(any(b'getBatteryLevel' in op for op in operations))
                    self.assertTrue(all(b'getBatteryLevel' in op or b'getUseServices' in op for op in operations))
                finally:
                    server.shutdown();server.server_close();thread.join(timeout=5)

    @unittest.skipUnless(shutil.which('chromium'),'Chromium unavailable')
    def test_battery_browser_actual_percentage_zero_invalid_and_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'battery.js').write_bytes((ROOT/'device/unified/battery.js').read_bytes())
            (root/'index.html').write_text('''<!doctype html><div id="nimbus-global-controls"></div>
<script>
Object.defineProperty(document,'hidden',{get:()=>false});
window.setInterval=fn=>{window.batteryPoll=fn;return 1};
window.sample='<nimbus errcode="0"><level>100</level><status>charge</status></nimbus>';
window.fetch=async(path,options)=>{
 if(path!='/NimbusAPI'||options.method!='POST'||!options.body.includes('operation="getBatteryLevel"'))throw Error('Unexpected request');
 if(window.unavailable)throw Error('Offline');
 return {ok:true,text:async()=>window.sample};
};
</script><script src="battery.js"></script><script>
(async()=>{
 const checks=[];const wait=()=>new Promise(resolve=>setTimeout(resolve,50));
 await wait();const badge=document.getElementById('nimbus-home-battery');
 checks.push(badge.textContent==='Battery: 100% · Charging');
 checks.push(badge.dataset.charging==='true');
 window.sample='<nimbus errcode="0"><level>0</level><status>discharge</status></nimbus>';window.batteryPoll();await wait();
 checks.push(badge.textContent==='Battery: 0% · Discharging');
 for(const bad of ['101','-1','4.2','unknown']){
  window.sample='<nimbus errcode="0"><level>'+bad+'</level><status>charge</status></nimbus>';window.batteryPoll();await wait();
  checks.push(badge.textContent==='Battery: Unknown'&&window.NIMBUS_LIVE_BATTERY.capacity===null);
 }
 window.sample='<nimbus errcode="1"><level>100</level><status>charge</status></nimbus>';window.batteryPoll();await wait();
 checks.push(badge.textContent==='Battery: Unknown');
 window.unavailable=true;window.batteryPoll();await wait();checks.push(badge.textContent==='Battery: Unknown');
 document.body.dataset.checks=checks.map(Number).join('');
 document.body.dataset.test=checks.every(Boolean)?'PASS':'FAIL';
})().catch(error=>{document.body.dataset.test='ERROR';document.body.dataset.error=error.message});
</script>''')
            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self,*args):pass
            server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                result=subprocess.run(['chromium','--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
                                       '--disable-background-networking','--no-first-run','--user-data-dir='+str(root/'chrome'),
                                       '--virtual-time-budget=3000','--dump-dom',f'http://127.0.0.1:{server.server_port}/'],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr[-2000:])
                self.assertIn('data-test="PASS"',result.stdout,result.stdout[-2500:])
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
