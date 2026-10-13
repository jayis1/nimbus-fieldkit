'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const nativeMode = /\/(storage|sdcard|dashboard)\//.test(location.pathname) || location.protocol === 'file:';
  const definitions = [
    ['network_health', 'Network health', '↔', 'Read routes and interface counters without changing your network.'],
    ['watchdog', 'Connection watchdog', '↻', 'Bounded, foreground health checks. No automatic reconnection.'],
    ['speed_tests', 'Speed tests', '↗', 'An explicit 10-second iperf client test on your authorized network.'],
    ['backup_vault', 'Verified backup vault', '▤', 'Copy one reviewed file and verify its SHA-256 checksum.'],
    ['offline_toolbox', 'Offline toolbox', '⌘', 'Local operating guides and project notes, available without Internet.'],
    ['storage_alerts', 'Storage alerts', '▥', 'Check free space and warn below 64 MiB. Never delete files.'],
    ['file_sync', 'File sync', '⇄', 'Explicit transfers to mounted storage. No silent folder syncing.'],
    ['pi_jobs', 'Pi A / Pi B requirements', '◈', 'GameHack uses pinned Wi-Fi SSH to A; A controls B over its own USB/data link. Dispatch and capture require separate qualification.'],
    ['local_git', 'Local Git repositories', '⑂', 'Create a new bare local repository when compatible Git is installed.'],
    ['encrypted_archives', 'Encrypted archive storage', '◇', 'Store pre-encrypted .age/.gpg files. Encrypt on GameHack first.']
  ];
  const knownIds = new Set(definitions.map(item => item[0]));
  const defaultRoot = '/mnt/storage/nimbus-fieldkit-v04';
  let data = null;
  let token = '';
  let privacy = false;
  let busy = false;
  let history = [];
  let lastTraffic = null;
  let currentCommand = null;
  const docs = ['DASHBOARD.md', 'TOGGLES.md', 'FEATURES.md', 'FIRMWARE-3.04-INSPECTION.md'];
  const text = (id, value) => { $(id).textContent = value; };
  const notice = (message, error = false) => { text('notice', message); $('notice').classList.toggle('error', error); };
  const bytes = value => {
    if (!Number.isFinite(Number(value)) || value === null) return '—';
    let amount = Number(value), unit = 0;
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit++; }
    return `${amount.toFixed(unit > 0 ? 1 : 0)} ${units[unit]}`;
  };
  const uptime = seconds => {
    if (!Number.isFinite(Number(seconds))) return '—';
    const hours = Math.floor(Number(seconds) / 3600);
    return hours >= 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : `${hours}h ${Math.floor(Number(seconds) / 60) % 60}m`;
  };
  function renderBattery() {
    const live=window.NIMBUS_LIVE_BATTERY;
    if (nativeMode && live && Date.now()-live.observedAt>=0 && Date.now()-live.observedAt<90000) {
      text('battery',live.capacity===null ? 'Unknown / battery API unavailable' : `${live.capacity}% / ${live.status} · device API`);
      return;
    }
    const capacity=data?.battery?.capacity;
    const valid=(typeof capacity==='number' && Number.isInteger(capacity) && capacity>=0 && capacity<=100);
    text('battery',valid ? `${capacity}% / ${data.battery.status || 'Unknown'} · snapshot` : 'Unknown / no measured battery percentage');
  }
  if (nativeMode) {
    window.addEventListener('nimbus-battery-updated',renderBattery);
    // Standalone native pages must not depend on the stock homepage creating
    // global controls. Load the same source beside this dashboard script.
    if (!window.NIMBUS_BATTERY_POLLING) {
      const batteryScript=window.document.createElement('script');
      batteryScript.src=new URL('battery.js',window.document.currentScript?.src || location.href).href;
      batteryScript.onerror=renderBattery;
      window.document.head.append(batteryScript);
    }
  }
  const create = (tag, className, value) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = value;
    return element;
  };
  const quote = value => "'" + String(value).replace(/'/g, "'\\''") + "'";
  const feature = id => (data?.features || []).find(item => item.id === id);
  const root = () => {
    const path = data?.install_path;
    return typeof path === 'string' && /^\/mnt\/(storage|sdcard)\/[A-Za-z0-9_./-]+$/.test(path) && !path.split('/').includes('..') ? path : defaultRoot;
  };
  function showView(view) {
    if (!['overview', 'features', 'network', 'vault', 'toolbox', 'security'].includes(view)) return;
    document.querySelectorAll('.view').forEach(element => element.classList.toggle('hidden', element.id !== `view-${view}`));
    document.querySelectorAll('.nav-item').forEach(element => element.classList.toggle('active', element.dataset.view === view));
    const names = {overview:'Overview', features:'Feature switches', network:'Network health', vault:'Vault & sync', toolbox:'Offline toolbox', security:'Security & access'};
    text('section-name', names[view]);
    historyReplace(view);
  }
  function historyReplace(view) { try { window.history.replaceState(null, '', `#${view}`); } catch (_) {} }
  async function api(path, body) {
    if (!token) throw new Error('Unlock the host session with the token printed in your terminal.');
    const response = await fetch(path, {cache:'no-store', method:body ? 'POST':'GET', headers:{Authorization:`Bearer ${token}`, ...(body ? {'Content-Type':'application/json'} : {})}, ...(body ? {body:JSON.stringify(body)} : {})});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `Request failed (${response.status})`);
    }
    return response;
  }
  async function snapshot() {
    if (nativeMode) {
      const response = await fetch(`state.json?v=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) throw new Error('Device telemetry unavailable (HTTP ' + response.status + '). Verify the installed publisher path and publish a snapshot through pinned SSH; Refresh only reads it. The topology is a design, not measured connectivity.');
      const result = await response.json();
      validateSnapshot(result);
      return result;
    }
    const mode = await (await api('/api/privacy')).json();
    privacy = mode.enabled;
    privacyDisplay();
    if (!privacy) {
      const native = await (await api('/api/native-state')).json();
      if (native.schema === 'nimbus-dashboard/v1') { validateSnapshot(native); return native; }
    }
    const host = await (await api('/api/status')).json();
    const values = {};
    for (const line of host.memory.split('\n')) { const match = line.match(/^(\w+):\s+(\d+)/); if (match) values[match[1]] = Number(match[2]); }
    return {scope:'host', hostname:host.hostname, firmware:host.platform, generated_at:Date.now()/1000,
      uptime_seconds:Number(host.uptime), memory:{total_bytes:(values.MemTotal || 0)*1024, reclaimable_estimate_bytes:((values.MemFree || 0)+(values.Buffers || 0)+(values.Cached || 0))*1024},
      storage:host.storage, battery:{capacity:null,status:'Unknown'}, network:{gateway:null,uplink:null,subnets:[],interfaces:host.interfaces.map(name => ({name,rx_bytes:null,tx_bytes:null,errors:null,drops:null}))}, features:[],vault:[]};
  }
  async function storageSnapshotReason() {
    if (!nativeMode) return '';
    const controller=new AbortController();
    const deadline=setTimeout(()=>controller.abort(),8000);
    try {
      const response=await fetch('/NimbusAPI',{method:'POST',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:{'Content-Type':'text/xml'},body:'<?xml version="1.0"?><nimbus api="1.0" operation="getUseServices"></nimbus>'});
      if(!response.ok)return '';
      const body=await response.text();if(body.length>16384)return '';
      const xml=new DOMParser().parseFromString(body,'application/xml');const node=xml.documentElement;
      if(xml.querySelector('parsererror')||node.nodeName!=='nimbus'||node.getAttribute('errcode')!=='0')return '';
      const msc=node.querySelector('MSCMode')?.textContent.trim();
      if(msc==='true') {
        text('disk-caption','USB access enabled; media snapshot unavailable');
        return ' USB access is enabled in vendor settings. Media-backed tools need mounted storage; do not mount it while a USB host owns it. No storage mode was changed.';
      }
      return msc==='false' ? ' The media publisher is missing or not published. Verify its installed path; no storage or services were changed.' : '';
    } catch (_) {return '';}
    finally {clearTimeout(deadline);}
  }
  function validateSnapshot(value) {
    if (!value || value.schema !== 'nimbus-dashboard/v1' || value.scope !== 'device' || !Array.isArray(value.features) || !Array.isArray(value.network?.interfaces) || value.features.length > 10 || value.network.interfaces.length > 64 || !Number.isFinite(value.generated_at)) throw new Error('Invalid native dashboard snapshot. No controls will be inferred.');
    if (value.features.some(item => !knownIds.has(item.id) || typeof item.enabled !== 'boolean' || typeof item.available !== 'boolean')) throw new Error('Invalid native feature state.');
  }
  async function refresh() {
    if (nativeMode) window.dispatchEvent(new CustomEvent('nimbus-battery-refresh-request'));
    if (busy || (!nativeMode && !token)) return;
    busy = true; $('refresh').disabled = true;
    try {
      const next = await snapshot();
      if (data?.scope !== next.scope || data?.hostname !== next.hostname) { history = []; lastTraffic = null; }
      data = next;
      render();
      if (!nativeMode) await loadHostFiles();
      document.body.dataset.loaded = 'true';
      notice(next.scope === 'device' ? 'Reading the device snapshot. Browser actions require authenticated terminal confirmation.' : 'HOST DATA ONLY — native SanDisk snapshot is unavailable or host privacy is enabled.');
      return true;
    } catch (error) {
      // Never leave old ON flags/measurements looking live after a failed refresh.
      data=null; history=[]; lastTraffic=null; document.body.dataset.loaded='false';
      for (const id of ['gateway','free','memory','enabled-count','hostname','uptime','firmware','rate','last-updated']) text(id,'—');
      text('scope','TELEMETRY UNAVAILABLE'); text('publisher','Snapshot unavailable');
      text('freshness','Snapshot unavailable'); text('enabled-caption','No current native settings');
      text('uplink-caption','No current route snapshot'); text('disk-caption','No current storage snapshot');
      $('freshness').classList.add('warning'); document.body.dataset.scope='unavailable';
      text('battery','Unknown'); text('interfaces','No current telemetry.'); text('subnets','No current telemetry.');
      text('services','No current service inventory.'); text('service-source','No current listener telemetry.');
      text('files','No current vault listing.'); text('file-count','—'); text('traffic-totals','No current samples.');
      $('traffic-bars').replaceChildren(); renderFeatures(); renderBattery();
      const storageReason=await storageSnapshotReason();
      notice(error.message+storageReason,true); return false;
    }
    finally { busy = false; $('refresh').disabled = false; }
  }
  function render() {
    document.body.dataset.scope = data.scope;
    text('scope', data.scope === 'device' ? 'NATIVE DEVICE SNAPSHOT' : 'HOST PROTOTYPE / NOT SANDISK');
    text('hostname', data.hostname || 'Unknown'); text('firmware', data.firmware || 'Unknown'); text('uptime', uptime(data.uptime_seconds));
    text('gateway', data.network.gateway || 'Not measured'); text('uplink-caption', data.network.uplink ? `${data.network.uplink} / route present, Internet not tested` : 'No device uplink route measured');
    text('free', bytes(data.storage.free)); text('disk-caption', `${bytes(data.storage.used)} used / ${bytes(data.storage.total)} total`);
    const total = Number(data.memory.total_bytes), free = Number(data.memory.reclaimable_estimate_bytes);
    text('memory', total > 0 ? `${Math.round(Math.max(0, total-free)/total*100)}%` : '—');
    text('enabled-count', data.features.length ? `${data.features.filter(item => item.enabled).length} / ${data.features.length}` : 'Not measured');
    text('enabled-caption', data.features.length ? 'Saved flags; not running tasks' : 'Host view has no native settings');
    renderBattery();
    text('publisher', data.publisher || 'Host inventory');
    const age = (Date.now()/1000) - data.generated_at;
    text('freshness', age < -60 ? 'Check device clock' : age > 60 ? `Snapshot ${Math.floor(age)}s old` : 'Recent snapshot');
    $('freshness').classList.toggle('warning', age > 60 || age < -60);
    text('last-updated', `Data timestamp: ${new Date(data.generated_at*1000).toLocaleTimeString()}`);
    renderFeatures(); renderNetwork(); renderTraffic(); renderServices();
    if (nativeMode) renderFiles(data.vault || [], true);
  }
  function renderFeatures() {
    const grid = $('feature-grid'); grid.replaceChildren();
    for (const [id, name, icon, description] of definitions) {
      const current = feature(id);
      const card = create('article', 'feature-card'); card.dataset.feature = id;
      const top = create('div', 'feature-top'); top.append(create('span', 'feature-icon', icon));
      const toggle = create('button', 'switch', current ? (current.enabled ? 'ON':'OFF') : 'UNKNOWN');
      toggle.type = 'button'; toggle.setAttribute('role', 'switch'); toggle.setAttribute('aria-label', `Prepare ${name} ${current?.enabled ? 'OFF':'ON'} command`); toggle.setAttribute('aria-checked', String(Boolean(current?.enabled)));
      toggle.disabled = !current || (!current.available && !current.enabled);
      toggle.title = current?.reason || 'Load native feature state first';
      toggle.onclick = () => openToggle(id); top.append(toggle);
      card.append(top, create('h3', '', name), create('p', '', description), create('div', 'feature-reason', current?.reason || 'Native prerequisites have not been measured.'));
      const bottom = create('div', 'feature-bottom'); bottom.append(create('span', `badge ${current?.available ? 'good':''}`, current ? (current.available ? 'Available':'Dependency missing') : 'No snapshot'));
      const run = create('button', 'button', id === 'pi_jobs' ? 'Requirements':'Prepare action'); run.type = 'button'; run.disabled = id !== 'pi_jobs' && (!current?.enabled || !current?.available); run.onclick = () => openAction(id); bottom.append(run); card.append(bottom); grid.append(card);
    }
  }
  function renderNetwork() {
    $('interfaces').replaceChildren();
    const visible = data.network.interfaces.filter(item => item.name !== 'lo' && !item.name.startsWith('mon.'));
    for (const item of visible) {
      const row = create('div', 'interface-row'); const left = create('div'); left.append(create('strong', '', item.name), create('small', '', item.name === data.network.uplink ? 'Default-route uplink' : 'Local interface'));
      const right = create('div', 'row-values', `RX ${bytes(item.rx_bytes)} / TX ${bytes(item.tx_bytes)}`); right.append(create('small', '', item.errors === null ? 'Counters not measured' : `${item.errors} errors / ${item.drops} drops`)); row.append(left,right); $('interfaces').append(row);
    }
    if (!visible.length) $('interfaces').append(create('p', '', 'No measured interface inventory.'));
    $('subnets').replaceChildren();
    for (const item of data.network.subnets || []) { const row=create('div','route-row'); const left=create('div');left.append(create('strong','',item.interface),create('small','',`Mask ${item.mask}`));row.append(left,create('span','row-values',item.address));$('subnets').append(row); }
    if (!data.network.subnets?.length) $('subnets').append(create('p','','No device subnet inventory loaded.'));
  }
  function renderTraffic() {
    const item = data.network.interfaces.find(item => item.name === data.network.uplink);
    if (item && Number.isFinite(item.rx_bytes) && lastTraffic && data.generated_at > lastTraffic.time && item.rx_bytes >= lastTraffic.rx) {
      const elapsed = data.generated_at-lastTraffic.time;
      const rate = (item.rx_bytes-lastTraffic.rx)/elapsed;
      history.push(rate); history=history.slice(-30); text('rate', `${bytes(rate)}/s RX`);
    }
    if (item && Number.isFinite(item.rx_bytes)) { lastTraffic={time:data.generated_at,rx:item.rx_bytes};text('traffic-totals', `RX ${bytes(item.rx_bytes)} · TX ${bytes(item.tx_bytes)}`); }
    $('traffic-bars').replaceChildren();
    if (!history.length) $('traffic-bars').append(create('span','empty-chart','Waiting for two updated uplink snapshots.'));
    const maximum=Math.max(1,...history);
    for (const value of history) { const bar=create('progress');bar.max=maximum;bar.value=value;bar.setAttribute('aria-label',`${bytes(value)} per second received`);$('traffic-bars').append(bar); }
  }
  function renderServices() {
    const names={ftp:'FTP / 21',telnet:'Telnet / 23',http:'HTTP / 80',ssh:'SSH / 22',https:'HTTPS port / 443'};
    $('services').replaceChildren(); text('service-source',data.services?.source || 'No device kernel listener inventory. Use the host probe or verify in the device terminal.');
    for (const [id,name] of Object.entries(names)) { const row=create('div','service-row');const value=data.services?.[id];row.append(create('strong','',name),create('span',`badge ${value && ['ftp','telnet','http'].includes(id) ? 'warning':''}`,value === undefined ? 'Unknown':value ? 'Listening':'Not listening'));$('services').append(row); }
  }
  function renderFiles(files, native) {
    $('files').replaceChildren();text('vault-title',native ? 'Native vault / current installation':'Host vault / not SanDisk');text('file-count',`${files.length} files`);
    if (!files.length) $('files').append(create('p','','No files listed. Use an explicit verified copy to add a reviewed file.'));
    for (const file of files) {
      if (typeof file.name !== 'string' || /[/\\]/.test(file.name) || file.name === '.' || file.name === '..') continue;
      const row=create('div','file-row');const left=create('div');left.append(create('strong','',file.name),create('small','',bytes(file.bytes)));const actions=create('div','input-row');
      const hash=create('button','button','SHA-256');hash.type='button';hash.onclick=()=>native ? openCommand('Hash selected file','Read-only hash of one explicitly selected vault file.',`sh nimbus-agent.sh hash ${quote(`${root()}/vault/${file.name}`)}`):run(hash,async()=>{const result=await(await api('/api/hash?name='+encodeURIComponent(file.name))).json();$('hash').classList.remove('hidden');text('hash',`${result.name} / ${result.sha256}`);});
      const download=create('button','button','Download');download.type='button';download.disabled=file.supported===false;download.onclick=()=>run(download,async()=>{const response=native ? await fetch('../vault/'+encodeURIComponent(file.name)) : await api('/api/download?name='+encodeURIComponent(file.name));if(!response.ok)throw new Error('Download unavailable.');const blob=new Blob([await response.arrayBuffer()],{type:'application/octet-stream'});const url=URL.createObjectURL(blob);const link=create('a');link.href=url;link.download=file.name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
      actions.append(hash,download);row.append(left,actions);$('files').append(row);
    }
  }
  async function loadHostFiles() { if (privacy) { text('files','File access blocked by local host privacy.');return; } const result=await(await api('/api/files')).json();renderFiles(result.files,false); }
  function makeDocs() {
    $('documents').replaceChildren();
    for (const name of docs) { const button=create('button','button',name);button.type='button';button.onclick=()=>run(button,async()=>{if(nativeMode && feature('offline_toolbox') && !feature('offline_toolbox').enabled)throw new Error('Offline toolbox is OFF. Enable it through Feature switches first.');const response=nativeMode ? await fetch('../docs/'+encodeURIComponent(name),{cache:'no-store'}):await api('/api/docs?name='+encodeURIComponent(name));if(!response.ok)throw new Error('Document unavailable in this installation.');text('document',await response.text());});$('documents').append(button); }
  }
  function openDialog() { const dialog=$('command-dialog'); if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open',''); }
  function closeDialog() { const dialog=$('command-dialog');if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open'); }
  function openCommand(title, description, command, inputs=[]) {
    text('command-title',title);text('command-description',description);$('command-inputs').replaceChildren();
    currentCommand=command;
    for (const item of inputs) {
      const label=create('label','',item.label);const input=create('input');input.id=`command-${item.id}`;input.type='text';input.placeholder=item.placeholder || '';input.setAttribute('aria-label',item.label);input.oninput=updateCommand;label.append(input);$('command-inputs').append(label);
    }
    updateCommand();openDialog();
  }
  function updateCommand() {
    if(currentCommand===null) {
      $('command-text').value='Architecture guidance only. Use GameHack’s Pi A / pinned Wi-Fi SSH menu; no SanDisk terminal command is needed.';
      $('copy-command').disabled=true;return;
    }
    try { const command=typeof currentCommand==='function' ? currentCommand():currentCommand;$('command-text').value=`cd ${quote(root())} || exit 1\n${command}`;$('copy-command').disabled=false; }
    catch(error) { $('command-text').value=error.message;$('copy-command').disabled=true; }
  }
  const inputValue = id => { const value=$(`command-${id}`).value.trim();if(!value)throw new Error('Fill the requested input to prepare the command.');return value; };
  function openToggle(id) {
    if(!knownIds.has(id))return;
    const current=feature(id);if(!current)return notice('Native feature state is unavailable.',true);
    const value=current.enabled ? 'off':'on';
    if(value==='on'&&!current.available)return notice(current.reason,true);
    const name=definitions.find(item=>item[0]===id)[1];
    openCommand(`Set ${name} ${value.toUpperCase()}`, 'This changes only a saved user-level flag. OFF blocks new operations; running finite copies finish. Watchdog OFF stops our loop without changing Wi-Fi.', `sh nimbus-agent.sh settings set ${id} ${value} &&\nsh nimbus-dashboard.sh snapshot`);
  }
  function openAction(id) {
    if(!knownIds.has(id))return;
    if(id==='pi_jobs')return openCommand('Pi A / Pi B architecture requirements','GameHack → pinned Wi-Fi SSH → Pi A → USB/data → Pi B. A stays managed; B needs verified monitor support, a separate identity and USB provisioning. Run task executes on A, not automatically on B. This SanDisk page neither pairs nor relays commands; keep keys off public storage.',null);
    const current=feature(id);
    if(!current?.available)return notice(current?.reason || 'Load native feature state before preparing this action.',true);
    if(!current.enabled)return openToggle(id);
    const name=definitions.find(item=>item[0]===id)[1];
    const prefix=`sh nimbus-agent.sh settings run ${id}`;
    if(['network_health','storage_alerts','offline_toolbox'].includes(id))return openCommand(name,'Explicit, read-only native operation.',`${prefix}\nsh nimbus-dashboard.sh snapshot`);
    if(id==='watchdog')return openCommand(name,'12 foreground reports every 10 seconds. Ctrl+C stops the loop. No reconnection or radio changes.',`${prefix} 12 10\nsh nimbus-dashboard.sh snapshot`);
    if(['backup_vault','encrypted_archives'].includes(id))return openCommand(name,'Choose one reviewed file, maximum 64 MiB. Existing outputs are never overwritten. Encryption must already have happened on GameHack.',()=>`${prefix} ${quote(inputValue('source'))} &&\nsh nimbus-dashboard.sh snapshot`,[{id:'source',label:'Absolute path to reviewed source file',placeholder:'/mnt/storage/report.txt'}]);
    if(id==='file_sync')return openCommand(name,'Only an explicit single-file transfer into an existing mounted/local directory. No automatic mount or remote FTP.',()=>`${prefix} ${quote(inputValue('source'))} ${quote(inputValue('destination'))} &&\nsh nimbus-dashboard.sh snapshot`,[{id:'source',label:'Absolute source file path',placeholder:'/mnt/storage/report.txt'},{id:'destination',label:'Existing destination directory',placeholder:'/mnt/sdcard/reports'}]);
    if(id==='local_git')return openCommand(name,'Create a new local bare repository. Requires Git; no network access or hooks are invoked.',()=>{const value=inputValue('name');if(!/^[A-Za-z0-9_.-]+$/.test(value)||['.','..'].includes(value))throw new Error('Use a simple new repository name.');return `${prefix} ${quote(value)}\nsh nimbus-dashboard.sh snapshot`;},[{id:'name',label:'New repository name',placeholder:'field-notes'}]);
    if(id==='speed_tests')return openCommand(name,'Only run against your own or explicitly authorized iperf server. The client test lasts 10 seconds.',()=>{const target=inputValue('target');const parts=target.split('.');if(parts.length!==4||parts.some(value=>!/^\d{1,3}$/.test(value)||Number(value)>255)||Number(parts[0])===0||Number(parts[0])>=224)throw new Error('Use a numeric unicast IPv4 target.');return `${prefix} ${quote(target)} authorized`;},[{id:'target',label:'Authorized iperf server IP',placeholder:'192.168.11.100'}]);
  }
  async function run(button, task) {button.disabled=true;try{await task();notice('Operation complete.');}catch(error){notice(error.message,true);}finally{button.disabled=false;}}
  function privacyDisplay() {text('privacy',privacy ? 'Disable local host privacy':'Enable local host privacy');text('privacy-state',privacy ? 'Local host privacy ON. No SanDisk service or radio was changed.':'Host privacy OFF. This is not a device firewall.');}
  function theme() {
    const next=document.documentElement.dataset.theme==='dark' ? 'light':'dark';document.documentElement.dataset.theme=next;
    try{localStorage.setItem('nimbus-theme',next);}catch(_){}
    $('theme').setAttribute('aria-label',next==='dark' ? 'Switch to light mode':'Switch to dark mode');
  }
  try { if(localStorage.getItem('nimbus-theme')==='light')document.documentElement.dataset.theme='light'; } catch (_) {}
  $('theme').setAttribute('aria-label',document.documentElement.dataset.theme==='dark' ? 'Switch to light mode':'Switch to dark mode');
  $('theme').onclick=theme;
  document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>showView(button.dataset.view));
  document.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>openAction(button.dataset.action));
  $('refresh').onclick=refresh;
  $('close-dialog').onclick=closeDialog;$('close-command').onclick=closeDialog;
  $('copy-command').onclick=()=>run($('copy-command'),async()=>{const value=$('command-text').value;try{if(!navigator.clipboard)throw new Error('Fallback');await navigator.clipboard.writeText(value);}catch(_){$('command-text').focus();$('command-text').select();if(!document.execCommand('copy'))throw new Error('Command selected. Copy it manually with Ctrl+C.');}notice('Command copied. Nothing executed; run it in your authenticated device session.');});
  $('publish-command').onclick=()=>openCommand('Publish one snapshot','Read local telemetry and saved settings. The browser reloads this file; it does not execute commands.','sh nimbus-dashboard.sh snapshot');
  $('publisher-command').onclick=()=>openCommand('Start bounded native publisher','Requires network_health and watchdog ON. Up to 120 snapshots at 15-second intervals (~30 minutes). Ctrl+C or toggling watchdog OFF stops it.','sh nimbus-dashboard.sh watch 120 15');
  $('connect').onclick=()=>run($('connect'),async()=>{token=$('token').value.trim();$('token').value='';if(await refresh()===false)throw new Error($('notice').textContent);});
  $('lock').onclick=()=>{token='';data=null;history=[];lastTraffic=null;document.body.dataset.loaded='false';for(const id of ['gateway','free','memory','enabled-count','hostname','firmware','uptime','last-updated','interfaces','subnets','files','document','diagnostic','node','hash'])text(id,'Session locked.');$('feature-grid').replaceChildren();$('traffic-bars').replaceChildren();$('services').replaceChildren();notice('Host session locked; token cleared from page memory.');};
  $('privacy').onclick=()=>run($('privacy'),async()=>{const result=await(await api('/api/privacy',{enabled:!privacy})).json();privacy=result.enabled;privacyDisplay();await refresh();});
  $('node-check').onclick=()=>run($('node-check'),async()=>{const result=await(await api('/api/node')).json();$('node').classList.remove('hidden');text('node',JSON.stringify(result,null,2));});
  $('check').onclick=()=>run($('check'),async()=>{if(!$('permission').checked)throw new Error('Confirm target authorization.');const parts=$('ports').value.split(',').map(value=>value.trim());if(parts.some(value=>!/^\d+$/.test(value)))throw new Error('Use comma-separated integer TCP ports.');const result=await(await api('/api/check',{target:$('target').value.trim(),ports:parts.map(Number),authorized:true})).json();text('diagnostic',JSON.stringify(result,null,2));});
  for(const action of ['ping','dns','routes'])$(action).onclick=()=>run($(action),async()=>{if(action!=='routes'&&!$('permission').checked)throw new Error('Confirm target authorization.');const result=await(await api('/api/diagnostic',{action,target:$('target').value.trim(),name:$('dns-name').value.trim(),authorized:$('permission').checked})).json();text('diagnostic',JSON.stringify(result,null,2));});
  document.querySelectorAll('.host-only').forEach(element=>element.classList.toggle('hidden',nativeMode));
  document.querySelectorAll('.native-only').forEach(element=>element.classList.toggle('hidden',!nativeMode));
  $('host-session').classList.toggle('hidden',nativeMode);
  $('stock-link').classList.toggle('hidden',!nativeMode);
  makeDocs();renderFeatures();showView(location.hash.slice(1)||'overview');
  if(nativeMode)refresh();else{notice('Host prototype: unlock with your terminal session token. No device telemetry is assumed.');text('scope','HOST PROTOTYPE');}
  setInterval(()=>{if(!document.hidden)refresh();},15000);
})();
