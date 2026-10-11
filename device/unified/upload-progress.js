/* Real multipart upload progress; never manufacture a timer-based percentage. */
'use strict';
(() => {
  const Upload = window.AjaxUpload;
  if (!Upload || window.NIMBUS_UPLOAD_PROGRESS) return;
  const originalSubmit = Upload.prototype.submit;
  const originalCancel = Upload.prototype.cancel;
  const outcome = text => {
    const raw = String(text || '').trim();
    if (!raw) return 'unknown';
    try {
      const data = JSON.parse(raw);
      const code = data?.nimbus?.errcode;
      if (code !== undefined && /^-?\d+$/.test(String(code))) return Number(code) === 0 ? 'success' : 'error';
    } catch (_) {}
    if (raw.startsWith('<')) {
      const xml = new DOMParser().parseFromString(raw, 'application/xml');
      if (!xml.querySelector('parsererror')) {
        const code = xml.querySelector('nimbus > errcode');
        if (code && /^-?\d+$/.test(code.textContent.trim())) return Number(code.textContent) === 0 ? 'success' : 'error';
      }
    }
    return 'unknown';
  };
  let panel;
  let label;
  let meter;
  const display = (percent, message) => {
    if (!panel) {
      const card = document.getElementById('div-short-block-msg');
      if (!card) return;
      panel = document.createElement('div'); panel.id = 'nimbus-upload-progress';
      label = document.createElement('p'); label.setAttribute('role', 'status');
      meter = document.createElement('progress'); meter.max = 100;
      meter.setAttribute('aria-label', 'Upload bytes sent');
      panel.append(label, meter); card.insertBefore(panel, document.getElementById('btnMessageCancel2'));
    }
    if (panel.hidden) panel.hidden = false;
    if (label.textContent !== message) label.textContent = message;
    // Repeated byte events in the same integer percentage need no DOM writes.
    if (percent === null) {
      if (meter.hasAttribute('value')) meter.removeAttribute('value');
    } else if (!meter.hasAttribute('value') || meter.value !== percent) meter.value = percent;
  };
  const hide = () => {if (panel) panel.hidden = true;};
  Upload.prototype.submit = function() {
    if (this._button?.id !== 'btnUpload' || !window.FormData || !window.XMLHttpRequest || !this._input?.files?.length) {
      return originalSubmit.apply(this, arguments);
    }
    if (this._nimbusActive) return;
    const xhr = new XMLHttpRequest();
    if (!xhr.upload) return originalSubmit.apply(this, arguments);
    const settings = this._settings;
    const files = this._input.files;
    const file = files[0].name;
    const extension = file.includes('.') ? file.slice(file.lastIndexOf('.') + 1) : '';
    if (settings.onSubmit.call(this, file, files, extension) === false) {this._clearInput(); return;}
    const state = {xhr, finished: false, computable: false};
    this._nimbusActive = state;
    this.disable(); display(0, '0% sent — starting upload');
    const finish = (kind, response) => {
      if (state.finished) return;
      state.finished = true; this._nimbusActive = null;
      this.enable(); this._clearInput(); hide();
      if (kind === 'success') settings.onComplete.call(this, file, response);
      else if (kind === 'error') settings.onError.call(this, file);
      else {
        window.t4u.elementUnblockUI();
        if (kind === 'unknown') {
          window.t4u.showMessage({title:'Upload response received', message:'Bytes were sent, but the device response did not confirm success. Check the destination folder before retrying.'});
          window.folderViewer?.reload?.(true);
        }
      }
    };
    xhr.upload.onprogress = event => {
      if (state.finished) return;
      if (!event.lengthComputable || event.total <= 0) {
        state.computable = false; display(null, 'Uploading — byte percentage unavailable'); return;
      }
      state.computable = true;
      const percent = Math.max(0, Math.min(100, Math.floor(event.loaded * 100 / event.total)));
      display(percent, percent === 100 ? '100% sent — waiting for device confirmation' : `${percent}% sent`);
    };
    xhr.upload.onload = () => {
      if (!state.finished) display(state.computable ? 100 : null, state.computable ? '100% sent — waiting for device confirmation' : 'Bytes sent — waiting for device confirmation');
    };
    xhr.onload = () => {
      if (state.finished) return;
      if (xhr.status < 200 || xhr.status >= 300 || xhr.responseURL && new URL(xhr.responseURL, location.href).origin !== location.origin) {
        finish('error'); return;
      }
      finish(outcome(xhr.responseText), xhr.responseText);
    };
    xhr.onerror = xhr.ontimeout = () => finish('error');
    xhr.onabort = () => finish('cancel');
    try {
      const action = new URL(settings.action, location.href);
      if (action.origin !== location.origin || action.pathname !== '/NimbusAPI/upload') throw new Error('Unexpected upload endpoint');
      const form = new FormData();
      for (const [key, value] of Object.entries(settings.data || {})) form.append(key, String(value));
      for (const selected of files) form.append(settings.name, selected, selected.name);
      xhr.open('POST', action.href, true);
      // Browser sets the multipart boundary. No retries, extra endpoints or shell API.
      xhr.send(form);
    } catch (_) {finish('error');}
  };
  Upload.prototype.cancel = function() {
    if (this._nimbusActive) {this._nimbusActive.xhr.abort(); return;}
    return originalCancel.apply(this, arguments);
  };
  window.NIMBUS_UPLOAD_PROGRESS = {outcome};
})();
