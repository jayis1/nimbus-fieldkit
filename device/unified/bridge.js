'use strict';
(() => {
  const nav = document.getElementById('btnNimbusFieldKit');
  const host = document.getElementById('nimbus-unified-host');
  if (!nav || !host) return;
  let started = false;
  let pendingView = 'overview';
  const prefix = '/data/fieldkit-v05/';
  document.documentElement.dataset.theme = 'dark';
  try { if (localStorage.getItem('nimbus-theme') === 'light') document.documentElement.dataset.theme = 'light'; } catch (_) {}
  const make = (tag, text) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const controls = make('div');
  controls.id = 'nimbus-global-controls';
  const launch = make('button', 'Quick jump · Ctrl+K');
  launch.type = 'button'; launch.id = 'nimbus-quick-jump';
  const theme = make('button', 'Theme');
  theme.type = 'button'; theme.id = 'nimbus-global-theme';
  const themeLabel = () => theme.setAttribute('aria-label', document.documentElement.dataset.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  themeLabel();
  theme.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('nimbus-theme', next); } catch (_) {}
  });
  new MutationObserver(themeLabel).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});
  controls.append(launch, theme);
  document.getElementById('navigator').append(controls);
  // Preserve stock web authentication: SSH is not a web-admin session.
  const login = document.getElementById('divLogin');
  const password = document.getElementById('setting-admin-password');
  if (login && password) {
    const signIn = make('button', 'Sign in'); signIn.type = 'button';
    signIn.id = 'nimbus-settings-sign-in';
    signIn.addEventListener('click', () => {
      if (password.disabled || !password.value) {password.focus(); return;}
      if (window.t4u?.SS?.AdminLoginSetting) window.t4u.SS.AdminLoginSetting();
    });
    login.append(signIn);
    const status = make('p'); status.id = 'nimbus-settings-access';
    status.setAttribute('role', 'status'); login.parentNode.insertBefore(status, login);
    const actions = [...document.querySelectorAll('.authority .lblBtn[id], .authority .setting-check-firmware-upgrade')];
    const updateAccess = () => {
      const locked = window.t4u?.SS?.isLogin ? !window.t4u.SS.isLogin() : true;
      status.textContent = locked ? 'Protected controls require the device web-admin password. SSH login does not sign you in here. Enter the password and select Sign in.' : 'Web-admin controls unlocked. Wi-Fi changes can disconnect clients; reset and format are destructive.';
      if (signIn.disabled !== password.disabled) signIn.disabled = password.disabled;
      for (const action of actions) {
        const disabled = locked || !!action.closest('.authority.disable');
        action.setAttribute('role', 'button'); action.setAttribute('aria-disabled', String(disabled));
        action.tabIndex = disabled ? -1 : 0;
      }
    };
    for (const action of actions) action.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && action.getAttribute('aria-disabled') === 'false') {
        event.preventDefault(); action.click();
      }
    });
    new MutationObserver(updateAccess).observe(login.parentNode, {subtree:true, attributes:true, attributeFilter:['class','disabled']});
    updateAccess();
  }
  const palette = make('dialog');
  palette.id = 'nimbus-jump-dialog';
  palette.setAttribute('aria-label', 'Jump to a device screen');
  const title = make('h2', 'Your field workspace');
  const hint = make('p', 'Navigate only. No device operation runs from this menu.');
  const search = make('input');
  search.type = 'search'; search.placeholder = 'Search screens and tools…';
  search.setAttribute('aria-label', 'Search screens and tools');
  const results = make('div'); results.className = 'nimbus-jump-results';
  const close = make('button', 'Close'); close.type = 'button';
  close.addEventListener('click', () => palette.close());
  const entries = [
    ['Files / uploads / folders', 'btnFolderView'], ['Photos / albums', 'btnPhotosView'],
    ['Videos', 'btnVideosView'], ['Music / playlists', 'btnMusicView'],
    ['Settings / Wi-Fi / administration', 'btnSetting'],
    ['FieldKit overview', null, 'overview'], ['Feature switches', null, 'features'],
    ['Network health / watchdog', null, 'network'], ['Vault / backup / sync', null, 'vault'],
    ['Offline docs / Pi worker', null, 'toolbox'], ['Security readiness', null, 'security']
  ];
  const selectView = view => {
    pendingView = view;
    nav.click();
    host.shadowRoot?.querySelector(`[data-view="${view}"]`)?.click();
  };
  const renderResults = () => {
    results.replaceChildren();
    const query = search.value.trim().toLowerCase();
    for (const [label, id, view] of entries) {
      if (!label.toLowerCase().includes(query)) continue;
      const button = make('button', label); button.type = 'button';
      button.addEventListener('click', () => {
        palette.close();
        if (id) document.getElementById(id).click(); else selectView(view);
      });
      results.append(button);
    }
    if (!results.children.length) results.append(make('p', 'No matching screen.'));
  };
  const openPalette = () => { search.value = ''; renderResults(); palette.showModal(); search.focus(); };
  search.addEventListener('input', renderResults);
  search.addEventListener('keydown', event => {
    if (event.key === 'Enter') {event.preventDefault(); results.querySelector('button')?.click();}
  });
  palette.append(title, hint, search, results, close);
  document.body.append(palette);
  launch.addEventListener('click', openPalette);
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault(); if (!palette.open) openPalette();
    }
  });
  for (const id of ['btnFolderView', 'btnPhotosView', 'btnVideosView', 'btnMusicView', 'btnSetting', 'btnHelp']) {
    document.getElementById(id)?.addEventListener('click', () => {
      document.body.classList.remove('nimbus-toolkit-open');
      nav.classList.remove('menuSelected');
    });
  }
  nav.addEventListener('click', async event => {
    event.preventDefault();
    document.body.classList.add('nimbus-toolkit-open');
    nav.classList.add('menuSelected');
    if (started) return;
    started = true;
    try {
      // Shadow DOM isolates our CSS/IDs from legacy jQuery selectors. No iframe.
      const surface = host.shadowRoot || host.attachShadow({mode: 'open'});
      surface.replaceChildren();
      const response = await fetch(prefix + 'toolkit.html', {cache: 'no-store'});
      if (!response.ok) throw new Error('Toolkit markup could not be loaded.');
      const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = prefix + 'toolkit.css';
      const styled = new Promise((resolve, reject) => {
        stylesheet.onload = resolve;
        stylesheet.onerror = () => reject(new Error('Toolkit styles could not be loaded.'));
      });
      surface.append(stylesheet, ...Array.from(parsed.body.childNodes));
      await styled;
      host.dataset.theme = document.documentElement.dataset.theme;
      new MutationObserver(() => {host.dataset.theme = document.documentElement.dataset.theme;}).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});
      window.NIMBUS_UNIFIED_SURFACE = surface;
      const script = document.createElement('script');
      script.src = prefix + 'toolkit.js';
      script.onload = () => {
        surface.querySelector(`[data-view="${pendingView}"]`)?.click();
        const security = surface.getElementById('view-security');
        const panel = make('article'); panel.className = 'panel';
        panel.append(make('h2', 'Hardening readiness — not yet verified'), make('p', 'Telnet retirement is a later step. A listening SSH port alone is not a secure replacement.'));
        const list = make('ol'); list.className = 'checklist';
        for (const label of ['Verified private backups: complete; disaster recovery still untested.', 'Maintained key-only SSH, pinned host key and two working sessions: not verified.', 'WPA2-AES configuration and strong unique passphrase: not verified.', 'SSH after reboot plus a recovery path: not verified.', 'Only then disable Telnet and other unnecessary legacy services.']) list.append(make('li', label));
        const guide = make('button', 'Read security transition plan'); guide.type = 'button'; guide.className = 'button';
        const preview = make('pre'); preview.hidden = true;
        guide.addEventListener('click', async () => {
          guide.disabled = true;
          try {
            const response = await fetch(prefix + 'SECURITY-PLAN.md', {cache:'no-store'});
            if (!response.ok) throw new Error('Plan unavailable. No settings changed.');
            preview.textContent = await response.text(); preview.hidden = false;
          } catch (error) {preview.textContent = error.message; preview.hidden = false;}
          finally {guide.disabled = false;}
        });
        panel.append(list, guide, preview); security.append(panel);
      };
      script.onerror = () => {
        started = false;
        surface.replaceChildren(make('p', 'Toolkit script unavailable. Click FieldKit to retry; stock controls remain accessible.'));
      };
      document.head.append(script);
    } catch (error) {
      const message = document.createElement('p');
      message.id = 'nimbus-integration-error';
      message.textContent = error.message + ' Stock file/media/settings controls remain accessible.';
      started = false;
      (host.shadowRoot || host).replaceChildren(message);
    }
  });
  // Selection remains available for reviewed commands without changing stock handlers.
  document.addEventListener('selectstart', event => {
    if (event.composedPath().includes(host)) event.stopPropagation();
  }, true);
})();
