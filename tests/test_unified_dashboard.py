import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import unittest

ROOT = Path(__file__).parents[1]
STOCK = ROOT / 'numbus-backup/stock-web.tar'
spec = importlib.util.spec_from_file_location('unified_build', ROOT / 'scripts/build-unified-dashboard.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@unittest.skipUnless(STOCK.exists(), 'Private stock web backup unavailable')
class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'candidate.tar'
        builder.build(STOCK, self.bundle)
        with tarfile.open(self.bundle) as archive:
            self.files = {member.name: archive.extractfile(member).read() for member in archive}
        with tarfile.open(STOCK) as archive:
            self.original = archive.extractfile('data/index.html').read().decode('utf-8-sig')

    def tearDown(self):
        self.temp.cleanup()

    def test_all_original_ids_and_scripts_retained(self):
        page = self.files['index.html'].decode()
        ids = lambda value: re.findall(r'id=["\']([^"\']+)', value)
        self.assertTrue(set(ids(self.original)).issubset(ids(page)))
        scripts = lambda value: re.findall(r'<script[^>]*src=["\']([^"\']+)', value)
        self.assertEqual(scripts(page)[:-2], scripts(self.original))
        self.assertEqual(scripts(page)[-2:], ['/data/fieldkit-v05/audio-html5.js', '/data/fieldkit-v05/bridge.js'])
        for identifier in ('btnUpload', 'btnDownload', 'btnDel', 'btnNew', 'btnFolderView', 'btnPhotosView', 'btnVideosView', 'btnMusicView', 'btnSetting', 'setting-connect-to-internet-popup', 'setting-format-nimbus', 'setting-check-firmware-upgrade'):
            self.assertIn(identifier, ids(page))
        self.assertIn('btnNimbusFieldKit', page)
        self.assertNotIn('<iframe', page)
        self.assertNotIn('<iframe', self.files['fieldkit-v05/toolkit.html'].decode())

    def test_hashes_reproducible_and_no_private_configuration(self):
        import hashlib
        manifest = json.loads(self.files['MANIFEST.json'])
        for entry in manifest['files']:
            self.assertEqual(hashlib.sha256(self.files[entry['name']]).hexdigest(), entry['sha256'])
        other=self.root/'second.tar';builder.build(STOCK, other)
        self.assertEqual(self.bundle.read_bytes(), other.read_bytes())
        self.assertFalse(any(name.endswith(('.bin','.db')) for name in self.files))
        self.assertNotIn('original-index.html', self.files)

    def test_installer_syntax_and_guards(self):
        script=self.root/'install.sh';script.write_bytes(self.files['install.sh'])
        subprocess.run(['sh','-n',str(script)],check=True)
        result=subprocess.run(['sh',str(script),'install'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('rollback)', script.read_text())
        self.assertNotIn('fw_setenv', script.read_text())
        self.assertNotIn('reboot', script.read_text())

    def test_ui_upgrade_preserves_existing_runtime_and_rollback(self):
        shipped=ROOT/'build/nimbus-unified-v05.tar'
        if not shipped.exists():self.skipTest('Shipped v0.5 bundle unavailable')
        output=self.root/'upgrade.tar'
        builder.build(STOCK,output,shipped)
        with tarfile.open(output) as archive:
            names=archive.getnames()
            manifest=json.load(archive.extractfile('MANIFEST.json'))
            script=archive.extractfile('install.sh').read().decode()
            js=archive.extractfile('fieldkit-v06/toolkit.js').read().decode()
        with tarfile.open(shipped) as archive:
            import hashlib
            previous_hash=hashlib.sha256(archive.extractfile('index.html').read()).hexdigest()
        self.assertEqual(manifest['version'],'0.6')
        self.assertEqual(manifest['expected_current_index_sha256'],previous_hash)
        self.assertFalse(any(name.startswith('native/') for name in names))
        self.assertIn('/storage/nimbus-unified-v05/native/dashboard/state.json',js)
        self.assertNotIn('import-settings',script)
        self.assertIn('Previous v0.5 homepage restored',script)
        self.assertIn('/mnt/storage/nimbus-unified-v06',script)
        self.assertIn('/mnt/storage/nimbus-unified-v05/native/nimbus-dashboard.sh',script)
        path=self.root/'upgrade.sh';path.write_text(script)
        subprocess.run(['sh','-n',str(path)],check=True)

    @unittest.skipUnless(shutil.which('google-chrome') or shutil.which('chromium'), 'Chrome/Chromium unavailable')
    def test_browser_same_page_navigation_theme_and_commands(self):
        # Serve the exact stock assets locally, never proxy requests to the drive.
        browser_files = self.files
        shipped = ROOT/'build/nimbus-unified-v05.tar'
        if shipped.exists():
            upgrade=self.root/'browser-upgrade.tar'
            builder.build(STOCK,upgrade,shipped)
            with tarfile.open(upgrade) as archive:
                browser_files={member.name:archive.extractfile(member).read() for member in archive}
        web=self.root/'web';web.mkdir()
        with tarfile.open(STOCK) as archive:
            for member in archive:
                if not member.isfile() or not member.name.startswith('data/') or '..' in Path(member.name).parts:
                    continue
                output=web/member.name;output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes(archive.extractfile(member).read())
        warning_spec = importlib.util.spec_from_file_location('browser_warning_fix', ROOT/'scripts/package-flash-warning-fix.py')
        warning_fix = importlib.util.module_from_spec(warning_spec); warning_spec.loader.exec_module(warning_fix)
        controller = web/'data/js/t4u.controller.js'
        controller.write_bytes(warning_fix.patch_controller(controller.read_bytes()))
        (web/'index.html').write_bytes(browser_files['index.html'].replace(b'</body>',b'<script src="/browser-test.js"></script></body>'))
        page = web/'index.html'
        page.write_bytes(page.read_bytes().replace(b'<head>', b'<head><script>Object.defineProperty(navigator,"userAgent",{value:"Mozilla/5.0 Firefox/128.0"});</script>', 1))
        for name, content in browser_files.items():
            if name.startswith('fieldkit-v'):
                output=web/'data'/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(content)
        snapshot={'schema':'nimbus-dashboard/v1','scope':'device','generated_at':1791687600,'install_path':'/mnt/storage/nimbus-unified-v05/native','hostname':'Browser fixture',
                  'uptime_seconds':3600,'firmware':'Test fixture','publisher':'manual','battery':{'capacity':None},'storage':{'free':100,'used':20,'total':120},
                  'memory':{'total_bytes':128000000,'reclaimable_estimate_bytes':64000000},'network':{'gateway':'172.16.10.254','uplink':'wlan1','interfaces':[],'subnets':[]},
                  'features':[{'id':name,'enabled':True,'available':True,'reason':'Test fixture'} for name in ('network_health','watchdog','speed_tests','backup_vault','offline_toolbox','storage_alerts','file_sync','pi_jobs','local_git','encrypted_archives')],'vault':[]}
        state=web/'storage/nimbus-unified-v05/native/dashboard/state.json';state.parent.mkdir(parents=True);state.write_text(json.dumps(snapshot))
        import wave
        music = web/'storage/audio fixture #1.WAV'
        with wave.open(str(music), 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
            audio.writeframes(b'\0\0' * 8000)
        (web/'browser-test.js').write_text('''
          (async()=>{
            const checks=[];
            checks.push(!document.body.textContent.includes('Please install Adobe'));
            checks.push(!document.body.textContent.includes('Your browser needs Flash'));
            // Exercise the real vendor busy/cancel lifecycle without sending an upload.
            const busy=document.getElementById('div-short-block-msg');
            checks.push(getComputedStyle(busy).display==='none');
            let cancelled=0;
            t4u.elementBlockUI('Uploading',()=>cancelled++);
            await new Promise(resolve=>setTimeout(resolve,100));
            checks.push(getComputedStyle(busy).display!=='none');
            checks.push(getComputedStyle(busy.querySelector('.loading')).display==='none');
            checks.push(getComputedStyle(busy,'::before').animationName===(matchMedia('(prefers-reduced-motion: reduce)').matches?'none':'nimbus-upload-spin'));
            checks.push(getComputedStyle(busy).borderRadius==='16px');
            const busyRect=busy.getBoundingClientRect();
            checks.push(busyRect.left>=0 && busyRect.right<=innerWidth);
            checks.push(getComputedStyle(document.getElementById('btnMessageCancel2')).height==='34px');
            document.getElementById('btnMessageCancel2').click();
            await new Promise(resolve=>setTimeout(resolve,500));
            checks.push(cancelled===1 && getComputedStyle(busy).display==='none');
            document.getElementById('nimbus-global-theme').click();
            checks.push(document.documentElement.dataset.theme==='light');
            t4u.elementBlockUI('Uploading');
            await new Promise(resolve=>setTimeout(resolve,100));
            checks.push(getComputedStyle(busy,'::before').borderTopColor==='rgb(8, 121, 108)');
            t4u.elementUnblockUI();
            await new Promise(resolve=>setTimeout(resolve,500));
            checks.push(getComputedStyle(busy).display==='none');
            document.getElementById('nimbus-global-theme').click();
            document.getElementById('nimbus-quick-jump').click();
            const palette=document.getElementById('nimbus-jump-dialog');
            checks.push(palette.open);
            const search=palette.querySelector('input');
            search.value='security';search.dispatchEvent(new Event('input'));
            checks.push(palette.querySelectorAll('.nimbus-jump-results button').length===1);
            palette.querySelector('.nimbus-jump-results button').click();
            checks.push(!palette.open);
            let host=document.getElementById('nimbus-unified-host');
            for(let i=0;i<120 && host.dataset.loaded!=='true';i++)await new Promise(resolve=>setTimeout(resolve,50));
            const surface=host.shadowRoot;
            checks.push(!surface.getElementById('view-security').classList.contains('hidden'));
            checks.push(surface.getElementById('view-security').textContent.includes('Hardening readiness'));
            surface.querySelector('[data-view="overview"]').click();
            checks.push(host.dataset.loaded==='true');
            checks.push(document.body.classList.contains('nimbus-toolkit-open'));
            checks.push(surface.querySelectorAll('.feature-card').length===10);
            checks.push(surface.getElementById('gateway').textContent==='172.16.10.254');
            checks.push(getComputedStyle(surface.getElementById('host-session')).display==='none');
            checks.push(getComputedStyle(surface.querySelector('.metrics')).display==='grid');
            checks.push(document.documentElement.dataset.theme==='dark');
            surface.getElementById('theme').click();
            await new Promise(resolve=>setTimeout(resolve,0));
            checks.push(document.documentElement.dataset.theme==='light' && host.dataset.theme==='light');
            surface.getElementById('theme').click();
            surface.querySelector('[data-view="features"]').click();
            surface.querySelector('[data-feature="network_health"] .switch').click();
            checks.push(surface.getElementById('command-dialog').open);
            checks.push(surface.getElementById('command-text').value.includes('settings set network_health off'));
            surface.getElementById('close-dialog').click();
            document.getElementById('btnSetting').click();
            checks.push(!document.body.classList.contains('nimbus-toolkit-open'));
            checks.push(document.getElementById('setting-format-nimbus')!==null);
            const signIn=document.getElementById('nimbus-settings-sign-in');
            const adminPassword=document.getElementById('setting-admin-password');
            const wifiAction=document.getElementById('setting-wifi-name');
            checks.push(signIn!==null && wifiAction.getAttribute('aria-disabled')==='true');
            checks.push(document.getElementById('nimbus-settings-access').textContent.includes('web-admin password'));
            // Mock only the stock login callback; never authenticate to a device.
            const originalLogin=window.t4u.SS.AdminLoginSetting;
            let attempts=0;window.t4u.SS.AdminLoginSetting=()=>attempts++;
            adminPassword.disabled=false;adminPassword.value='fixture-only';signIn.click();
            checks.push(attempts===1);
            window.t4u.SS.AdminLoginSetting=originalLogin;adminPassword.value='';
            let keyboardClicks=0;
            wifiAction.addEventListener('click',()=>keyboardClicks++);
            wifiAction.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
            checks.push(keyboardClicks===0);
            const originalToken=window.token;window.token='fixture-only';
            const authority=wifiAction.closest('.authority');authority.classList.remove('disable');
            authority.classList.add('fixture-access');
            await new Promise(resolve=>setTimeout(resolve,0));
            checks.push(wifiAction.getAttribute('aria-disabled')==='false' && wifiAction.tabIndex===0);
            wifiAction.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
            checks.push(keyboardClicks===1);
            window.token=originalToken;authority.classList.add('disable');
            checks.push(['btnFolderView','btnPhotosView','btnVideosView','btnMusicView','btnSetting'].every(id=>{
              const events=window.jQuery._data(document.getElementById(id),'events');
              return events && events.click && events.click.length>=1;
            }));
            checks.push(document.querySelectorAll('iframe').length===0);
            // Real vendor jPlayer + HTML5 adapter, served locally with synthetic PCM.
            checks.push(!!window.NIMBUS_HTML5_AUDIO);
            const song={path:'/storage/audio fixture #1.WAV', songname:'Fixture', artist:'Fixture', albumname:'Fixture', albumphoto:'/fixture.png'};
            const mapped=NIMBUS_HTML5_AUDIO.media(song);
            checks.push(mapped.track.wav==='/storage/audio%20fixture%20%231.WAV' && song.wav===undefined);
            checks.push(['javascript:bad','https://example.com/a.mp3','/storage/../a.mp3','/storage/%2e%2e/a.mp3'].every(path=>{
              try {NIMBUS_HTML5_AUDIO.media({path});return false;}catch(_){return true;}
            }));
            AudioPlayer.playlist=[song];AudioPlayer.onplay=()=>{};
            AudioPlayer.init('#audioComponents', {playlist:[song]});
            for(let i=0;i<80 && !AudioPlayer.inited;i++)await new Promise(resolve=>setTimeout(resolve,25));
            const jp=window.jQuery('#audioComponents');
            checks.push(jp.jPlayer('option','solution')==='html');
            const nativeAudio=document.querySelector('#audioComponents audio');
            checks.push(!!nativeAudio);
            if(nativeAudio) {
              nativeAudio.load();
              for(let i=0;i<80 && nativeAudio.readyState<2;i++)await new Promise(resolve=>setTimeout(resolve,25));
              checks.push(nativeAudio.readyState>=2 && nativeAudio.duration===1);
              await nativeAudio.play();checks.push(!nativeAudio.paused);
              nativeAudio.currentTime=0.5;checks.push(nativeAudio.currentTime===0.5);
              nativeAudio.pause();checks.push(nativeAudio.paused);
            }
            checks.push(document.querySelectorAll('#audioComponents object, #audioComponents embed').length===0);
            jp.trigger({type:window.jQuery.jPlayer.event.error,jPlayer:{error:{type:window.jQuery.jPlayer.error.NO_SUPPORT}}});
            checks.push(document.getElementById('nimbus-audio-feedback').textContent.includes('codec'));
            checks.push(!document.getElementById('nimbus-audio-feedback').textContent.includes('install Flash'));
            checks.push(!document.body.textContent.includes('Please install Adobe'));
            checks.push(!document.body.textContent.includes('Your browser needs Flash'));
            document.body.dataset.unifiedTest=checks.every(Boolean)?'passed':JSON.stringify(checks);
            document.getElementById('btnNimbusFieldKit').click();
            surface.querySelector('[data-view="overview"]').click();
          })().catch(error=>{document.body.dataset.unifiedTest=error.message;});
        ''')
        class Quiet(SimpleHTTPRequestHandler):
            writes=[]
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                type(self).writes.append(body)
                self.send_error(503,'Offline test fixture; device APIs deliberately unavailable')
        http=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(web)))
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            profile_root = os.environ.get('NIMBUS_BROWSER_TMPDIR') or ('/tmp/opencode' if Path('/tmp/opencode').is_dir() else None)
            with tempfile.TemporaryDirectory(dir=profile_root,prefix='unified-browser-') as profile:
                screenshot = str(Path(profile_root or profile) / 'nimbus-unified-browser.png')
                command=[shutil.which('google-chrome') or shutil.which('chromium'),'--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--autoplay-policy=no-user-gesture-required',
                    '--no-first-run','--user-data-dir='+profile,'--window-size=1440,1050','--screenshot='+screenshot,'--virtual-time-budget=9000','--dump-dom',f'http://127.0.0.1:{http.server_port}/']
                result=subprocess.run(command,capture_output=True,text=True,timeout=40)
                self.assertEqual(result.returncode,0,result.stderr[-2000:])
                self.assertIn('data-unified-test="passed"',result.stdout)
                reduced=subprocess.run(command+['--force-prefers-reduced-motion','--window-size=390,844'],capture_output=True,text=True,timeout=40)
                self.assertEqual(reduced.returncode,0,reduced.stderr[-2000:])
                self.assertIn('data-unified-test="passed"',reduced.stdout)
                for body in Quiet.writes:
                    self.assertNotRegex(body.decode(errors='replace'),r'(?i)formatNimbus|resetNimbus|upgradeFirmware|setSSID|settings set')
        finally:
            http.shutdown();http.server_close();thread.join()
