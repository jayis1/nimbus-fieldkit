/* First-party HTML5-only adapter for the vendor Music view. No Flash fallback. */
'use strict';
(() => {
  const $ = window.jQuery;
  const player = window.AudioPlayer;
  if (!$?.fn?.jPlayer || !player || window.NIMBUS_HTML5_AUDIO) return;
  const formats = {mp3: 'mp3', m4a: 'm4a', ogg: 'oga', oga: 'oga', wav: 'wav', wave: 'wav'};
  let status;
  let download;
  const feedback = message => {
    if (!status) {
      const panel = document.createElement('div');
      panel.id = 'nimbus-audio-feedback';
      panel.style.cssText = 'position:fixed;bottom:100px;left:16px;right:16px;z-index:10000;padding:12px;background:#202936;color:#fff;border-radius:8px';
      status = document.createElement('span'); status.setAttribute('role', 'status');
      download = document.createElement('a'); download.textContent = ' Open/download original';
      download.style.color = '#9ed3ff'; download.hidden = true;
      download.target = '_blank'; download.rel = 'noopener';
      const close = document.createElement('button'); close.type = 'button'; close.textContent = 'Dismiss';
      close.addEventListener('click', () => {panel.hidden = true;});
      panel.append(status, download, close); document.body.append(panel);
    }
    status.textContent = message;
    status.parentNode.hidden = false;
  };
  const media = song => {
    const raw = typeof song?.path === 'string' ? song.path : '';
    // Device media only. Encode individual raw filename segments, including #/?/%.
    // No arbitrary schemes, cross-origin URLs, traversal or credential-bearing URLs.
    if (!/^\/(storage|sdcard)\//.test(raw) || /[\\\u0000-\u001f\u007f]/.test(raw) || raw.split('/').some(part => part === '.' || part === '..' || /%(2e|2f|5c|00)/i.test(part))) {
      throw new Error('This track does not have a supported device-media path.');
    }
    const url = raw.split('/').map(encodeURIComponent).join('/');
    const extension = raw.slice(raw.lastIndexOf('.') + 1).toLowerCase();
    const format = formats[extension];
    const result = {...song, path: raw};
    // Remove stale format URLs, while retaining metadata for vendor playlist callbacks.
    for (const key of Object.keys(formats)) delete result[key];
    if (format) result[format] = url;
    if (download) {download.href = url; download.hidden = false;}
    return {track: result, url, format};
  };
  const originalPlugin = $.fn.jPlayer;
  $.fn.jPlayer = function(options, ...args) {
    if (options && typeof options === 'object' && this.is('#audioComponents')) {
      const ready = options.ready;
      options = {...options, solution: 'html', supplied: 'mp3,m4a,oga,wav', preload: 'metadata'};
      delete options.swfPath; delete options.wmode;
      options.ready = function(event) {
        const audio = this.querySelector('audio');
        if (audio && !audio.dataset.nimbusPromiseHandling) {
          audio.dataset.nimbusPromiseHandling = 'true';
          const play = audio.play.bind(audio);
          audio.play = () => {
            const promise = play();
            return promise?.catch(error => {
              player.isplaying = false;
              $(player.cssSelector.play).show(); $(player.cssSelector.pause).hide();
              feedback(error.name === 'NotAllowedError' ? 'Tap Play to allow audio playback in this browser.' : 'Playback failed. Check the file and your connection, or open the original in another player.');
            });
          };
        }
        if (ready) ready.call(this, event);
      };
    }
    return originalPlugin.call(this, options, ...args);
  };
  player.preventCache = song => {
    try {
      const result = media(song);
      if (!result.format) {
        feedback('This format is not supported by the browser Music player. Open/download the original for another player.');
        download.href = result.url; download.hidden = false;
      } else if (status) {status.parentNode.hidden = true;}
      return result.track;
    } catch (error) {
      feedback(error.message); download.removeAttribute('href'); download.hidden = true;
      return {path: ''};
    }
  };
  const originalInit = player.init;
  player.init = function(...args) {
    const result = originalInit.apply(this, args);
    // Vendor init binds its Flash-install suggestion in a ready callback. Replace
    // just that namespaced Music error handler after it has been registered.
    $(document).ready(() => {
      const component = $('#audioComponents');
      component.off($.jPlayer.event.error + '.myProject');
      component.off($.jPlayer.event.error + '.nimbusHtml5');
      component.on($.jPlayer.event.error + '.nimbusHtml5', () => {
        feedback('This browser could not play the track. Its codec may be unsupported, or the file/network may be unavailable. Open the original in another player.');
        try {const result = media(player.playlist[player.playindex]); download.href = result.url; download.hidden = false;} catch (_) {download.hidden = true;}
        player.isplaying = false;
        $(player.cssSelector.play).show(); $(player.cssSelector.pause).hide();
      });
    });
    return result;
  };
  window.NIMBUS_HTML5_AUDIO = {media};
})();
