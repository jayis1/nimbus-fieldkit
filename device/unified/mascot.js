/* Nib: original decorative desktop buddy. No AI, network, telemetry or mouse history. */
'use strict';
(() => {
  if (document.getElementById('nimbus-mascot') || document.getElementById('nimbus-buddy-toggle')) return;
  const key = 'nimbus-mascot-hidden-v1';
  const mount = () => {
  if (document.getElementById('nimbus-mascot')) return;
  try {if (localStorage.getItem(key) === 'yes') return;} catch (_) {}
  const host = document.createElement('div'); host.id = 'nimbus-mascot';
  const root = host.attachShadow({mode:'open'});
  root.innerHTML = `<style>
    :host{position:fixed;left:16px;bottom:16px;width:92px;height:108px;z-index:9000;pointer-events:none;color:#7cebd3;--buddy-panel:#172232;--buddy-line:#7cebd3;--buddy-eye:#e9f0f7;--buddy-ink:#15263b}
    :host([data-theme=light]){color:#08796c;--buddy-panel:#edf2f7;--buddy-line:#08796c;--buddy-eye:#fff}
    :host([hidden]){display:none!important}
    svg{width:92px;height:96px;overflow:visible;filter:drop-shadow(0 4px 6px #0003)}
    button{position:absolute;right:0;top:0;pointer-events:auto;width:24px;height:24px;padding:0;border:1px solid var(--buddy-line);border-radius:50%;background:var(--buddy-panel);color:var(--buddy-line);font:16px/20px system-ui;cursor:pointer}
    button:focus-visible{outline:2px solid var(--buddy-line);outline-offset:3px}
    p{margin:-2px 0 0;text-align:center;color:var(--buddy-line);font:600 11px/1 system-ui}
  </style>
  <svg viewBox="0 0 92 96" aria-hidden="true" focusable="false">
    <path d="M29 15v-5h34v5M14 40l-8 8 8 9m64-17 8 8-8 9M28 80l-5 8h13m28-8 5 8H56" fill="none" stroke="var(--buddy-line)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="16" y="15" width="60" height="65" rx="14" fill="var(--buddy-panel)" stroke="var(--buddy-line)" stroke-width="3"/>
    <path d="M30 23h32" stroke="var(--buddy-line)" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="34" cy="43" rx="10" ry="12" fill="var(--buddy-eye)"/>
    <ellipse cx="58" cy="43" rx="10" ry="12" fill="var(--buddy-eye)"/>
    <circle class="pupil" cx="34" cy="43" r="4" fill="var(--buddy-ink)"/>
    <circle class="pupil" cx="58" cy="43" r="4" fill="var(--buddy-ink)"/>
    <path d="M35 64q11 9 22 0" fill="none" stroke="var(--buddy-line)" stroke-width="3" stroke-linecap="round"/>
  </svg><p>Nib · FieldKit</p><button type="button" aria-label="Hide Nib, the decorative FieldKit buddy" title="Hide buddy">×</button>`;
  document.body.append(host);
  const pupils = [...root.querySelectorAll('.pupil')];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const fine = matchMedia('(pointer: fine)');
  const bar = document.getElementById('floatingbar');
  let pointer = null;
  let frame = null;
   let dismissed = false;
   let layoutDirty = true;
   let geometryDirty = true;
   let rect = null;
   const paint = () => {
     frame = null;
     if (dismissed || document.hidden) return;
     const theme = document.documentElement.dataset.theme || 'dark';
     if (host.dataset.theme !== theme) host.dataset.theme = theme;
     // Pointer frames reuse geometry: no computed-style/query/reflow per move.
     if (layoutDirty) {
       const bottom = bar && getComputedStyle(bar).display !== 'none' ? '110px' : '16px';
       if (host.style.bottom !== bottom) {host.style.bottom = bottom;geometryDirty = true;}
       layoutDirty = false;
     }
     if (geometryDirty) {rect = host.getBoundingClientRect();geometryDirty = false;}
    const follow = pointer && fine.matches && !reduced.matches && rect.width > 0;
    for (let i=0;i<pupils.length;i++) {
      const x = follow ? pointer.x-(rect.left+(i===0?34:58)) : 0;
      const y = follow ? pointer.y-(rect.top+43) : 0;
      const distance = Math.hypot(x,y);
      const scale = distance > 0 ? Math.min(3.5,distance/30)/distance : 0;
       const transform = `translate(${(x*scale).toFixed(2)} ${(y*scale).toFixed(2)})`;
       if (pupils[i].getAttribute('transform') !== transform) pupils[i].setAttribute('transform',transform);
    }
  };
   const schedule = () => {if (!dismissed && !document.hidden && frame === null) frame=requestAnimationFrame(paint);};
   const layout = () => {layoutDirty=true;schedule();};
   const bounds = () => {geometryDirty=true;layout();};
  const move = event => {
    if (event.pointerType !== 'mouse' || !fine.matches || reduced.matches) return;
    pointer = {x:event.clientX,y:event.clientY}; schedule();
  };
  const reset = () => {pointer=null;schedule();};
   const visibility = () => {
     pointer=null;
     if (document.hidden) {if (frame!==null) cancelAnimationFrame(frame);frame=null;}
     else bounds();
   };
  const themeObserver = new MutationObserver(schedule);
  themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
   const layoutObserver = new MutationObserver(layout);
   if (bar) layoutObserver.observe(bar,{attributes:true,attributeFilter:['style','class','hidden']});
  document.addEventListener('pointermove',move,{passive:true});
  document.documentElement.addEventListener('pointerleave',reset,{passive:true});
  document.addEventListener('visibilitychange',visibility);
  window.addEventListener('blur',reset);
   window.addEventListener('resize',bounds,{passive:true});
   window.visualViewport?.addEventListener('resize',bounds,{passive:true});
   window.visualViewport?.addEventListener('scroll',bounds,{passive:true});
  reduced.addEventListener('change',reset);fine.addEventListener('change',reset);
  root.querySelector('button').addEventListener('click',() => {
    dismissed=true;
    try {localStorage.setItem(key,'yes');} catch (_) {}
    if (frame!==null) cancelAnimationFrame(frame);
    themeObserver.disconnect();layoutObserver.disconnect();
    document.removeEventListener('pointermove',move);
    document.documentElement.removeEventListener('pointerleave',reset);
    document.removeEventListener('visibilitychange',visibility);
     window.removeEventListener('blur',reset);window.removeEventListener('resize',bounds);
     window.visualViewport?.removeEventListener('resize',bounds);
     window.visualViewport?.removeEventListener('scroll',bounds);
    reduced.removeEventListener('change',reset);fine.removeEventListener('change',reset);
    host.remove();
  });
  schedule();
  };
  const controls = document.getElementById('nimbus-global-controls');
  if (controls) {
    const toggle = document.createElement('button');toggle.type='button';toggle.id='nimbus-buddy-toggle';
    toggle.textContent='Show / hide buddy';
    toggle.addEventListener('click',() => {
      const existing=document.getElementById('nimbus-mascot');
      if (existing) existing.shadowRoot.querySelector('button').click();
      else {try {localStorage.removeItem(key);} catch (_) {} mount();}
    });
    controls.append(toggle);
  }
  mount();
})();
