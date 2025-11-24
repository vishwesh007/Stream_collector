// Firefox injected script (shared logic) - embedded link extraction & monitoring
// Reused from Chrome version; minimal changes for cross-browser compatibility.
(function(){
  'use strict';
  const SAFE_MAX_LEN = 64 * 1024;
  function report(type, url, meta){
    if (!url || typeof url !== 'string') return;
    window.postMessage({ source:'stream-capture-injected', action:'captureStream', type, url, meta, ts:Date.now() }, '*');
  }
  function extractEmbedded(text, parentUrl){
    if (!text) return;
    const urlRegex = /(https?:\/\/[^\s"'<>]+\.(?:m3u8|mpd|mp4|webm|mkv|m4s|ts)(?:\?[^\s"'<>]*)?)|([A-Za-z0-9_\-\/\.]+\.(?:m3u8|mpd)(?:\?[^\s"'<>]*)?)/gi;
    const licenseRegex = /(https?:\/\/[^\s"'<>]+(?:license|widevine|playready|fairplay)[^\s"'<>]*)/gi;
    const found = new Set(); let m;
    while ((m = urlRegex.exec(text)) !== null) { const u = m[1] || m[2]; if (u && u.length < 4096) found.add(u); }
    while ((m = licenseRegex.exec(text)) !== null) { const u = m[1]; if (u && u.length < 4096) found.add(u); }
    for (const u of found) report('embedded', resolveIfRelative(u, parentUrl), { source:'response-body', parent: parentUrl });
  }
  function resolveIfRelative(candidate, parentUrl){ try { if (/^https?:/i.test(candidate)) return candidate; return new URL(candidate, new URL(parentUrl)).href; } catch(_) { return candidate; } }
  const originalFetch = window.fetch;
  window.fetch = function(...args){ let reqUrl; try { const req = args[0]; reqUrl = typeof req === 'string' ? req : req && req.url; if (reqUrl && /\.(m3u8|mpd|mp4|webm|mkv)(\?.*)?$/i.test(reqUrl)) report('fetch', reqUrl, { method: (args[1] && args[1].method) || 'GET' }); } catch(_){}
    const p = originalFetch.apply(this, args);
    p.then(res => { try { const ct = res.headers.get('content-type') || ''; if (/text|json|xml|mpegurl|dash\+xml|application\/vnd\.apple\.mpegurl/i.test(ct)) { res.clone().arrayBuffer().then(buf => { const slice = buf.byteLength > SAFE_MAX_LEN ? buf.slice(0, SAFE_MAX_LEN) : buf; const text = new TextDecoder('utf-8').decode(slice); extractEmbedded(text, reqUrl || res.url); }); } } catch(_){} });
    return p;
  };
  const xhrOpen = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(method, url, ...rest){ this.__usc_url=url; this.__usc_method=method; return xhrOpen.apply(this, [method, url, ...rest]); };
  const xhrSend = XMLHttpRequest.prototype.send; XMLHttpRequest.prototype.send = function(body){ try { const url = this.__usc_url; if (url && /\.(m3u8|mpd|mp4|webm|mkv|ts|m4s)(\?.*)?$/i.test(url)) report('xhr', url, { method:this.__usc_method }); } catch(_){}
    this.addEventListener('load', () => { try { const url = this.__usc_url; const ct = this.getResponseHeader('content-type') || ''; let txt=''; if (this.responseType==='' || this.responseType==='text') txt = this.responseText || ''; else if (/text|json|xml|mpegurl|dash\+xml|application\/vnd\.apple\.mpegurl/i.test(ct)) txt = this.responseText || ''; if (txt) extractEmbedded(txt.substring(0, SAFE_MAX_LEN), url); } catch(_){} });
    return xhrSend.apply(this, [body]); };
  const observer = new MutationObserver(muts => { for (const m of muts) { for (const n of m.addedNodes) { if (n && n.tagName === 'VIDEO') hookVideo(n); } } }); observer.observe(document.documentElement, { childList:true, subtree:true }); Array.from(document.querySelectorAll('video')).forEach(hookVideo);
  function hookVideo(video){ const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(video), 'src'); if (desc && desc.set && !video.__usc_wrapped){ Object.defineProperty(video,'src',{ configurable:true, enumerable:desc.enumerable, get(){ return desc.get.call(this); }, set(val){ if (val && typeof val === 'string' && val.length < 2048) report('video-src', val, {}); return desc.set.call(this, val); } }); video.__usc_wrapped=true; } }
  if (navigator.requestMediaKeySystemAccess){ const origReq = navigator.requestMediaKeySystemAccess.bind(navigator); navigator.requestMediaKeySystemAccess = function(keySystem, configs){ try { report('drm', location.href, { keySystem, configsLength: configs?.length || 0 }); } catch(_){} return origReq(keySystem, configs); }; }
  console.log('[Stream Capture][Firefox] injected hooks active');
})();
