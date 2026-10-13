'use strict';
(() => {
  // One device query stream for homepage and standalone/native toolkit alike.
  if (window.NIMBUS_BATTERY_POLLING) return;
  window.NIMBUS_BATTERY_POLLING=true;
  const parent = document.getElementById('nimbus-global-controls');
  const badge = document.createElement('span');
  badge.id = 'nimbus-home-battery';
  badge.setAttribute('role', 'status'); badge.setAttribute('aria-live', 'polite');
  badge.style.cssText = 'display:inline-flex;align-items:center;gap:7px;padding:7px 9px;border:1px solid currentColor;border-radius:7px;font:12px/1.4 system-ui;white-space:nowrap;color:#8c9cb1';
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 26 16'); svg.setAttribute('width', '26'); svg.setAttribute('height', '16');
  svg.setAttribute('aria-hidden', 'true');
  svg.style.flexShrink='0';
  const rect = (x,y,width,height) => {
    const node = document.createElementNS(ns, 'rect');
    for (const [key,value] of Object.entries({x,y,width,height})) node.setAttribute(key,String(value));
    return node;
  };
  const outline=rect(1,1,21,14); outline.setAttribute('rx','2'); outline.setAttribute('fill','none'); outline.setAttribute('stroke','currentColor');
  const tip=rect(23,5,2,6); tip.setAttribute('fill','currentColor');
  const fill=rect(4,4,0,8); fill.setAttribute('fill','currentColor');
  svg.append(outline,tip,fill);
  const label=document.createElement('span'); label.textContent='Battery: Unknown';
  label.style.cssText='white-space:normal;overflow-wrap:anywhere;min-width:0';
  badge.append(svg,label); parent?.prepend(badge);

  function parseBattery(text) {
    const xml=new DOMParser().parseFromString(text,'application/xml');
    const root=xml.documentElement;
    if (xml.querySelector('parsererror') || root.nodeName!=='nimbus' ||
        (root.getAttribute('errcode') || root.getAttribute('errorcode'))!=='0') throw new Error('Battery API refused');
    const raw=root.querySelector('level')?.textContent.trim();
    if (typeof raw!=='string' || !/^(100|[0-9]{1,2})$/.test(raw)) throw new Error('Battery percentage unavailable');
    const status=root.querySelector('status')?.textContent.trim().toLowerCase();
    const states={charge:'Charging',charging:'Charging',discharge:'Discharging',discharging:'Discharging',full:'Full','not charging':'Not charging'};
    return {capacity:Number(raw),status:states[status] || 'Unknown',source:'vendor-battery-api',observedAt:Date.now()};
  }
  function render(value) {
    window.NIMBUS_LIVE_BATTERY=value;
    const known=value.capacity!==null;
    const text=known ? `Battery: ${value.capacity}%${value.status==='Unknown'?'':' · '+value.status}` : 'Battery: Unknown';
    if (label.textContent!==text) label.textContent=text;
    badge.setAttribute('aria-label',text);
    badge.title=known ? 'Read from the device battery API; not inferred from USB or voltage.' : 'Battery API unavailable or invalid; no percentage is assumed.';
    badge.dataset.charging=String(value.status==='Charging');
    badge.style.color=known ? (value.capacity<=15 ? '#f4bc70' : '#7cebd3') : '#8c9cb1';
    fill.setAttribute('width',known ? String(15*value.capacity/100) : '0');
    window.dispatchEvent(new CustomEvent('nimbus-battery-updated',{detail:value}));
  }
  let busy=false;
  async function refreshBattery() {
    if (busy || document.hidden) return;
    busy=true;
    const controller=new AbortController();
    const deadline=setTimeout(()=>controller.abort(),8000);
    try {
      // Stock read-only getBatteryLevel RPC. No admin token, service/radio change
      // or settings command; POST is only the vendor API's query transport.
      const response=await fetch('/NimbusAPI',{method:'POST',credentials:'same-origin',cache:'no-store',
        headers:{'Content-Type':'text/xml'},signal:controller.signal,
        body:'<?xml version="1.0"?><nimbus api="1.0" operation="getBatteryLevel"></nimbus>'});
      if (!response.ok) throw new Error('Battery request unavailable');
      const text=await response.text();
      if (text.length>16384) throw new Error('Battery response too large');
      render(parseBattery(text));
    } catch (_) { render({capacity:null,status:'Unknown',source:'vendor-battery-api',observedAt:Date.now()}); }
    finally { clearTimeout(deadline); busy=false; }
  }
  refreshBattery();
  setInterval(refreshBattery,30000);
  window.addEventListener('nimbus-battery-refresh-request',refreshBattery);
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)return;
    const last=window.NIMBUS_LIVE_BATTERY;
    if(last && Date.now()-last.observedAt>=90000)render({capacity:null,status:'Unknown',source:'vendor-battery-api',observedAt:Date.now()});
    refreshBattery();
  });
})();
