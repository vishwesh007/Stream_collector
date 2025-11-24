// Firefox content script - similar to Chrome version, with browser API fallback
(function(){
  const api = typeof browser !== 'undefined' ? browser : chrome;
  console.log('[Stream Capture][Firefox] content script loaded');
  api.storage.local.get({ usc_advanced: false }).then(cfg => { if (cfg.usc_advanced) injectAdvanced(); }).catch(()=>{});
  function injectAdvanced(){ if (window.__usc_injected) return; window.__usc_injected = true; const s = document.createElement('script'); s.src = api.runtime.getURL('injected.js'); s.onload = function(){ this.remove(); }; (document.head||document.documentElement).appendChild(s); }
  window.addEventListener('message', evt => {
    const data = evt.data; if (!data || data.source !== 'stream-capture-injected') return;
    if (data.action === 'captureStream' && data.url) {
      api.runtime.sendMessage({ action:'captureInjectedStream', url:data.url, type:data.type, meta:data.meta||{}, ts:data.ts, origin: location.href }).catch(()=>{});
    }
  });
  api.runtime.onMessage.addListener(msg => { if (msg.action === 'uscToggleAdvanced' && msg.enabled) injectAdvanced(); });
})();
