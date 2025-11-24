// Firefox background script (MV2) - adapted from MV3 service worker version
// Uses persistent background; adds browser API compatibility wrapper.
(function() {
  const api = typeof browser !== 'undefined' ? browser : chrome;
  console.log('[Universal Stream Capture][Firefox] Background loaded');

  const capturedStreams = new Map();
  const harData = new Map(); // Store HAR data per tab
  const streamPatterns = {
    m3u8: /\.m3u8(\?.*)?$/i,
    mpd: /\.mpd(\?.*)?$/i,
    ts: /\.ts(\?.*)?$/i,
    m4s: /\.m4s(\?.*)?$/i,
    youtube: /googlevideo\.com/i,
    hotstar: /hotstar\.com/i,
    netflix: /netflix\.com.*\/(range|manifest)/i,
    prime: /primevideo\.com/i,
    disney: /disneyplus\.com/i,
    hulu: /hulu\.com/i,
    videojs: /video\.js/i,
    wistia: /wistia\.com/i,
    vimeo: /vimeo\.com.*\/(progressive|playlist\.json)/i,
    jwplayer: /jwpcdn\.com/i,
    blob: /^blob:/i,
    data: /^data:video/i,
    mp4: /\.mp4(\?.*)?$/i,
    webm: /\.webm(\?.*)?$/i,
    mkv: /\.mkv(\?.*)?$/i,
  };
  const drmPatterns = {
    widevine: /widevine/i,
    playready: /playready/i,
    fairplay: /fairplay/i,
    clearkey: /clearkey/i,
    license: /license/i,
    drm: /drm/i,
    pssh: /pssh/i,
  };

  function captureStream(details) {
    const url = details.url;
    const tabId = details.tabId;
    if (tabId < 0) return;
    
    // Capture HAR data
    captureHAREntry(details);
    
    let streamType = 'unknown';
    let isDRM = false;
    for (const [type, pattern] of Object.entries(streamPatterns)) {
      if (pattern.test(url)) { streamType = type; break; }
    }
    for (const [type, pattern] of Object.entries(drmPatterns)) {
      if (pattern.test(url)) { isDRM = true; streamType = streamType === 'unknown' ? 'drm' : `${streamType}-drm`; break; }
    }
    if (streamType === 'unknown' && !isDRM) {
      // can't see response headers here (onBeforeRequest) so defer to later events
    }
    const headers = {};
    if (details.requestHeaders) {
      details.requestHeaders.forEach(h => { headers[h.name] = h.value; });
    }
    const stream = {
      url,
      type: streamType,
      isDRM,
      tabId,
      timestamp: Date.now(),
      method: details.method,
      headers,
      initiator: details.originUrl || details.documentUrl || 'unknown',
      validation: {
        status: 'pending',
        contentType: undefined,
        sizeBytes: undefined,
        playlistType: undefined,
        reason: undefined,
        resolution: undefined,
        width: undefined,
        height: undefined,
        bandwidth: undefined,
        variants: undefined
      }
    };
    if (!capturedStreams.has(tabId)) capturedStreams.set(tabId, []);
    const streams = capturedStreams.get(tabId);
    if (streams.some(s => s.url === url)) return;
    streams.push(stream);
    if (streams.length > 150) streams.shift();
    updateBadge(tabId, streams.length);
    persistStreams();
    if (shouldValidate(stream)) enqueueValidation(stream, tabId); else {
      stream.validation.status = 'unsupported';
      stream.validation.reason = 'Not a top-level playlist or media file';
    }
  }

  function updateBadge(tabId, count) {
    if (api.browserAction && api.browserAction.setBadgeText) {
      api.browserAction.setBadgeText({ text: count > 0 ? String(count) : '' , tabId });
      api.browserAction.setBadgeBackgroundColor({ color: count > 0 ? '#0A0' : '#666', tabId });
    }
  }

  api.webRequest.onBeforeRequest.addListener(captureStream, { urls: ["<all_urls>"] });
  api.webRequest.onSendHeaders.addListener(captureStream, { urls: ["<all_urls>"] }, ["requestHeaders"]);
  api.webRequest.onHeadersReceived.addListener(details => {
    const { url, tabId } = details;
    if (tabId < 0) return;
    
    // Capture HAR response data
    captureHARResponse(details);
    
    const streams = capturedStreams.get(tabId); if (!streams) return;
    const entry = streams.find(s => s.url === url); if (!entry) return;
    if (details.responseHeaders) {
      const ctHeader = details.responseHeaders.find(h => h.name.toLowerCase() === 'content-type');
      const clHeader = details.responseHeaders.find(h => h.name.toLowerCase() === 'content-length');
      if (ctHeader) entry.validation.contentType = ctHeader.value;
      if (clHeader) entry.validation.sizeBytes = parseInt(clHeader.value) || undefined;
    }
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);

  api.tabs.onRemoved.addListener(tabId => { 
    capturedStreams.delete(tabId); 
    harData.delete(tabId);
  });

  // HAR data capture functions
  function captureHAREntry(details) {
    const tabId = details.tabId;
    if (tabId < 0) return;
    
    if (!harData.has(tabId)) {
      harData.set(tabId, {
        log: {
          version: '1.2',
          creator: {
            name: 'Firefox',
            version: '123.0'
          },
          browser: {
            name: 'Firefox',
            version: '123.0'
          },
          pages: [],
          entries: []
        }
      });
    }
    
    const har = harData.get(tabId);
    
    // Check if entry already exists for this requestId
    let entry = har.log.entries.find(e => e._requestId === details.requestId);
    
    if (!entry) {
      // Create new HAR entry matching Firefox DevTools exact format
      entry = {
        pageref: 'page_1',
        startedDateTime: new Date().toISOString(),
        time: 0,
        request: {
          method: details.method || 'GET',
          url: details.url,
          httpVersion: 'HTTP/1.1',
          headers: [],
          queryString: [],
          cookies: [],
          headersSize: -1,
          bodySize: -1
        },
        response: {
          status: 0,
          statusText: '',
          httpVersion: 'HTTP/1.1',
          headers: [],
          cookies: [],
          content: {
            size: 0,
            mimeType: 'text/plain'
          },
          redirectURL: '',
          headersSize: -1,
          bodySize: -1
        },
        cache: {},
        timings: {
          blocked: -1,
          dns: -1,
          connect: -1,
          send: 0,
          wait: 0,
          receive: 0,
          ssl: -1
        },
        _requestId: details.requestId,
        _timestamp: Date.now()
      };
      
      // Parse query string from URL
      try {
        const urlObj = new URL(details.url);
        urlObj.searchParams.forEach((value, name) => {
          entry.request.queryString.push({ name, value });
        });
      } catch (e) {}
      
      har.log.entries.push(entry);
      
      // Limit entries to prevent memory issues
      if (har.log.entries.length > 300) {
        har.log.entries.shift();
      }
    }
    
    // Always update headers if present (called from onSendHeaders)
    if (details.requestHeaders) {
      entry.request.headers = [];
      entry.request.cookies = [];
      
      details.requestHeaders.forEach(h => {
        entry.request.headers.push({ name: h.name, value: h.value });
        
        // Extract cookies from Cookie header
        if (h.name.toLowerCase() === 'cookie') {
          const cookieStrings = h.value.split(/;\s*/);
          cookieStrings.forEach(cookieStr => {
            const eqIndex = cookieStr.indexOf('=');
            if (eqIndex > 0) {
              entry.request.cookies.push({
                name: cookieStr.substring(0, eqIndex).trim(),
                value: cookieStr.substring(eqIndex + 1).trim()
              });
            }
          });
        }
      });
    }
  }
  
  function captureHARResponse(details) {
    const tabId = details.tabId;
    if (tabId < 0) return;
    
    const har = harData.get(tabId);
    if (!har) return;
    
    // Find the matching request entry by requestId
    const entry = har.log.entries.find(e => e._requestId === details.requestId);
    if (!entry) return;
    
    // Calculate timing
    if (entry._timestamp) {
      entry.time = Date.now() - entry._timestamp;
      entry.timings.wait = entry.time;
    }
    
    // Update response data
    entry.response.status = details.statusCode || 200;
    entry.response.statusText = 'OK'; // Always use OK per DevTools standard
    
    if (details.responseHeaders) {
      entry.response.headers = [];
      entry.response.cookies = [];
      
      details.responseHeaders.forEach(h => {
        entry.response.headers.push({ name: h.name, value: h.value });
        
        // Extract Set-Cookie headers as cookies
        if (h.name.toLowerCase() === 'set-cookie') {
          const cookieParts = h.value.split(/;\s*/);
          const nameValue = cookieParts[0];
          const eqIndex = nameValue.indexOf('=');
          
          if (eqIndex > 0) {
            const cookie = {
              name: nameValue.substring(0, eqIndex).trim(),
              value: nameValue.substring(eqIndex + 1).trim()
            };
            
            // Parse optional cookie attributes
            for (let i = 1; i < cookieParts.length; i++) {
              const part = cookieParts[i].trim();
              const attrEqIndex = part.indexOf('=');
              
              if (attrEqIndex > 0) {
                const attrName = part.substring(0, attrEqIndex).trim().toLowerCase();
                const attrValue = part.substring(attrEqIndex + 1).trim();
                
                if (attrName === 'expires') cookie.expires = attrValue;
                else if (attrName === 'path') cookie.path = attrValue;
                else if (attrName === 'domain') cookie.domain = attrValue;
              } else {
                const attrName = part.toLowerCase();
                if (attrName === 'secure') cookie.secure = true;
                else if (attrName === 'httponly') cookie.httpOnly = true;
              }
            }
            
            entry.response.cookies.push(cookie);
          }
        }
        
        // Extract content metadata
        if (h.name.toLowerCase() === 'content-type') {
          entry.response.content.mimeType = h.value.split(';')[0].trim();
        }
        if (h.name.toLowerCase() === 'content-length') {
          const size = parseInt(h.value) || 0;
          entry.response.content.size = size;
          entry.response.bodySize = size;
        }
      });
    }
  }


  api.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getStreams') {
      const streams = capturedStreams.get(request.tabId) || [];
      sendResponse({ streams });
    } else if (request.action === 'getHAR') {
      const har = harData.get(request.tabId);
      if (har) {
        // Add page info if not already present
        if (har.log.pages.length === 0) {
          api.tabs.get(request.tabId).then(tab => {
            har.log.pages.push({
              startedDateTime: new Date().toISOString(),
              id: 'page_' + request.tabId,
              title: tab.url || 'Unknown',
              pageTimings: {}
            });
          }).catch(() => {});
        }
        sendResponse({ har: har });
      } else {
        sendResponse({ har: null });
      }
      return true;
    } else if (request.action === 'getStreamHAR') {
      const har = harData.get(request.tabId);
      if (har) {
        // Include ALL streaming-related entries (m3u8, mpd, mp4, ts, m4s, etc.)
        // This ensures we capture the full request/response chain including authentication cookies
        const streamingPatterns = [
          /\.m3u8(\?.*)?$/i,
          /\.mpd(\?.*)?$/i,
          /\.mp4(\?.*)?$/i,
          /\.ts(\?.*)?$/i,
          /\.m4s(\?.*)?$/i,
          /\.webm(\?.*)?$/i,
          /master_hs\.m3u8/i,
          /\.m3u$/i
        ];
        
        const relatedEntries = har.log.entries.filter(e => {
          const url = e.request.url.toLowerCase();
          return streamingPatterns.some(pattern => pattern.test(url));
        });
        
        if (relatedEntries.length > 0) {
          // Clean up internal properties and non-standard fields from entries
          const cleanedEntries = relatedEntries.map(e => {
            const cleaned = JSON.parse(JSON.stringify(e)); // Deep clone
            delete cleaned._requestId;
            delete cleaned._timestamp;
            delete cleaned.serverIPAddress;
            delete cleaned.connection;
            return cleaned;
          });
          
          // Get page info first, then send response
          api.tabs.get(request.tabId).then(tab => {
            const filteredHAR = {
              log: {
                version: '1.2',
                creator: {
                  name: 'Firefox',
                  version: '123.0'
                },
                browser: {
                  name: 'Firefox', 
                  version: '123.0'
                },
                pages: [{
                  startedDateTime: new Date().toISOString(),
                  id: 'page_1',
                  title: tab.url || '',
                  pageTimings: {
                    onContentLoad: -1,
                    onLoad: -1
                  }
                }],
                entries: cleanedEntries
              }
            };
            sendResponse({ har: filteredHAR });
          }).catch(() => {
            // Fallback without tab info
            const filteredHAR = {
              log: {
                version: '1.2',
                creator: {
                  name: 'Firefox',
                  version: '123.0'
                },
                browser: {
                  name: 'Firefox', 
                  version: '123.0'
                },
                pages: [{
                  startedDateTime: new Date().toISOString(),
                  id: 'page_1',
                  title: '',
                  pageTimings: {
                    onContentLoad: -1,
                    onLoad: -1
                  }
                }],
                entries: cleanedEntries
              }
            };
            sendResponse({ har: filteredHAR });
          });
          return true;
        } else {
          sendResponse({ har: null });
        }
      } else {
        sendResponse({ har: null });
      }
      return true;
    } else if (request.action === 'revalidateStream') {
      const streams = capturedStreams.get(request.tabId) || [];
      const stream = streams.find(s => s.url === request.url);
      if (!stream) { sendResponse({ success:false, error:'Not found'}); return; }
      stream.validation.status = 'pending'; stream.validation.reason = undefined;
      validateStream(stream, request.tabId).then(() => {
        sendResponse({ success:true, validation: stream.validation });
      }).catch(err => {
        stream.validation.status='error'; stream.validation.reason = err.message || 'Validation failed';
        sendResponse({ success:false, validation: stream.validation });
      });
      return true;
    } else if (request.action === 'clearStreams') {
      capturedStreams.delete(request.tabId); updateBadge(request.tabId, 0); sendResponse({ success:true });
    } else if (request.action === 'exportStreams') {
      const streams = capturedStreams.get(request.tabId) || []; sendResponse({ streams });
    } else if (request.action === 'captureInjectedStream') {
      const tabId = sender.tab && sender.tab.id; if (!tabId && tabId !== 0) { sendResponse({success:false}); return; }
      const url = request.url; if (!url) { sendResponse({ success:false }); return; }
      if (!capturedStreams.has(tabId)) capturedStreams.set(tabId, []);
      const list = capturedStreams.get(tabId);
      if (!list.some(s => s.url === url)) {
        let streamType = 'injected';
        for (const [type, pattern] of Object.entries(streamPatterns)) { if (pattern.test(url)) { streamType = type; break; } }
        const stream = {
          url,
          type: streamType,
          isDRM: /license|drm|widevine|playready|fairplay/i.test(url),
          tabId,
          timestamp: request.ts || Date.now(),
            method: request.meta?.method || 'INJECTED',
          headers: {},
          initiator: request.origin || 'injected',
          metadata: request.meta || {},
          source: request.meta?.source || 'injected',
          parent: request.meta?.parent || undefined,
          validation: { status: 'pending', reason: undefined }
        };
        list.push(stream);
        if (shouldValidate(stream)) enqueueValidation(stream, tabId); else { stream.validation.status='unsupported'; stream.validation.reason='Not a top-level playlist or media file'; }
        updateBadge(tabId, list.length); persistStreams();
      }
      sendResponse({ success:true });
    }
    return true;
  });

  // Persistence
  function persistStreams() {
    const obj = {}; for (const [tabId, list] of capturedStreams.entries()) obj[tabId] = list;
    api.storage.local.set({ __usc_streams: obj });
  }
  function restoreStreams() {
    api.storage.local.get('__usc_streams').then(data => {
      if (data && data.__usc_streams) {
        for (const [tabIdStr, list] of Object.entries(data.__usc_streams)) {
          const tabId = parseInt(tabIdStr); if (!isNaN(tabId) && Array.isArray(list)) { capturedStreams.set(tabId, list); updateBadge(tabId, list.length); }
        }
        console.log('[Stream Capture][Firefox] Restored streams');
      }
    }).catch(()=>{});
  }
  restoreStreams();

  // Validation queue
  const validationQueue = []; let validating = false;
  function enqueueValidation(stream, tabId) { validationQueue.push({ stream, tabId }); }
  function processValidationQueue() {
    if (validating) return; const item = validationQueue.shift(); if (!item) return; validating = true;
    validateStream(item.stream, item.tabId).catch(err => { item.stream.validation.status='error'; item.stream.validation.reason = err.message || 'Validation failed'; })
      .finally(() => { validating = false; persistStreams(); setTimeout(processValidationQueue, 250); });
  }
  setInterval(() => { if (!validating) processValidationQueue(); }, 1000);

  function shouldValidate(stream) {
    if (stream.isDRM) return true; const url = stream.url;
    if (/\.m3u8(\?.*)?$/i.test(url)) return true;
    if (/\.mpd(\?.*)?$/i.test(url)) return true;
    if (/\.(mp4|webm|mkv)(\?.*)?$/i.test(url)) return true;
    if (/googlevideo\.com/.test(url) && url.includes('mime=')) return true;
    return false;
  }

  async function validateStream(stream, tabId) {
    const url = stream.url; const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const res = await fetch(url, { method: 'GET', headers: buildValidationHeaders(stream), signal: controller.signal });
      clearTimeout(timeout);
      const contentType = res.headers.get('content-type') || stream.validation.contentType; if (contentType) stream.validation.contentType = contentType;
      const size = res.headers.get('content-length'); if (size) stream.validation.sizeBytes = parseInt(size) || undefined;
      let textSample = '';
      if (contentType && /application\/(vnd\.apple\.mpegurl|dash\+xml)|text|mpegurl|xml/i.test(contentType)) {
        const text = await res.text(); textSample = text.substring(0, 8192);
      } else if (/\.m3u8(\?.*)?$/i.test(url) || /\.mpd(\?.*)?$/i.test(url)) {
        const text = await res.text().catch(()=> ''); textSample = text.substring(0, 8192);
      }
      classifyPlaylist(stream, textSample);
      if (stream.validation.playlistType === 'file' && /\.(mp4|webm)(\?.*)?$/i.test(url)) await probeVideoResolution(stream);
      stream.validation.status='ok'; if (stream.validation.playlistType==='segment') stream.validation.reason='Segment file; need parent playlist';
    } catch (err) {
      stream.validation.status='error'; stream.validation.reason = err.name === 'AbortError' ? 'Timeout while validating' : (err.message || 'Unknown fetch error');
    } finally { clearTimeout(timeout); }
  }

  function classifyPlaylist(stream, textSample) {
    const url = stream.url;
    if (/\.m3u8(\?.*)?$/i.test(url)) {
      if (/#EXT-X-STREAM-INF/i.test(textSample)) { stream.validation.playlistType='master'; parseM3U8Resolution(stream, textSample); }
      else if (/#EXTINF:/i.test(textSample)) { stream.validation.playlistType='variant'; }
      else if (/#EXTM3U/i.test(textSample)) { stream.validation.playlistType='variant'; }
      else { stream.validation.playlistType='segment'; }
    } else if (/\.mpd(\?.*)?$/i.test(url)) {
      if (/Period/i.test(textSample) && /AdaptationSet/i.test(textSample)) { stream.validation.playlistType='manifest'; parseMPDResolution(stream, textSample); }
      else { stream.validation.playlistType='segment'; }
    } else if (/\.(mp4|webm|mkv)(\?.*)?$/i.test(url)) { stream.validation.playlistType='file'; }
    else if (stream.isDRM) { stream.validation.playlistType='drm'; }
  }

  function parseM3U8Resolution(stream, text) {
    const lines = text.split('\n'); const variants = [];
    for (const lineRaw of lines) {
      const line = lineRaw.trim(); if (line.startsWith('#EXT-X-STREAM-INF:')) {
        const attrs = parseM3U8Attributes(line); const resolution = attrs.RESOLUTION || ''; const bandwidth = parseInt(attrs.BANDWIDTH) || 0;
        if (resolution || bandwidth) variants.push({ resolution, bandwidth });
      }
    }
    if (variants.length) {
      variants.sort((a,b)=> b.bandwidth - a.bandwidth); const best = variants[0];
      if (best.resolution) { stream.validation.resolution = best.resolution; const [w,h] = best.resolution.split('x').map(v => parseInt(v)); if (w && h) { stream.validation.width=w; stream.validation.height=h; } }
      stream.validation.bandwidth = best.bandwidth;
      stream.validation.variants = variants.map(v => ({ res: v.resolution, bw: Math.round(v.bandwidth/1000)+'k'}));
    }
  }
  function parseM3U8Attributes(line) {
    const attrs = {}; const regex = /([A-Z-]+)=("([^"]*)"|([^,]*))/g; let m; while ((m = regex.exec(line)) !== null) { attrs[m[1]] = m[3] || m[4]; } return attrs; }

  function parseMPDResolution(stream, text) {
    const reps = []; const repRegex = /<Representation[^>]*>/gi; let m; while ((m = repRegex.exec(text)) !== null) {
      const tag = m[0]; const width = parseInt(tag.match(/width="(\d+)"/i)?.[1]) || 0; const height = parseInt(tag.match(/height="(\d+)"/i)?.[1]) || 0; const bandwidth = parseInt(tag.match(/bandwidth="(\d+)"/i)?.[1]) || 0; if (width && height) reps.push({ width, height, bandwidth });
    }
    if (reps.length) {
      reps.sort((a,b)=> b.bandwidth - a.bandwidth); const best = reps[0];
      stream.validation.resolution = `${best.width}x${best.height}`; stream.validation.width = best.width; stream.validation.height = best.height; stream.validation.bandwidth = best.bandwidth;
      stream.validation.variants = reps.map(r => ({ res: `${r.width}x${r.height}`, bw: Math.round(r.bandwidth/1000)+'k'}));
    }
  }

  async function probeVideoResolution(stream) {
    try {
      const url = stream.url; const res = await fetch(url, { method:'GET', headers:{ 'Range':'bytes=0-65535', ...buildValidationHeaders(stream) } });
      const buffer = await res.arrayBuffer(); const view = new DataView(buffer);
      if (/\.mp4(\?.*)?$/i.test(url)) { const dims = parseMP4Dimensions(view); if (dims) { stream.validation.width=dims.width; stream.validation.height=dims.height; stream.validation.resolution=`${dims.width}x${dims.height}`; } }
      else if (/\.webm(\?.*)?$/i.test(url)) { const dims = parseWebMDimensions(view); if (dims) { stream.validation.width=dims.width; stream.validation.height=dims.height; stream.validation.resolution=`${dims.width}x${dims.height}`; } }
    } catch (err) { console.log('[Stream Capture][Firefox] Resolution probe failed:', err.message); }
  }
  function parseMP4Dimensions(view) {
    let offset = 0; while (offset < view.byteLength - 8) {
      const size = view.getUint32(offset, false); const type = String.fromCharCode(view.getUint8(offset+4), view.getUint8(offset+5), view.getUint8(offset+6), view.getUint8(offset+7));
      if (type === 'tkhd' && size > 84) {
        const version = view.getUint8(offset+8); const widthOffset = version === 0 ? offset+76 : offset+88; const heightOffset = version === 0 ? offset+80 : offset+92;
        if (widthOffset + 4 <= view.byteLength && heightOffset + 4 <= view.byteLength) {
          const width = view.getUint32(widthOffset,false) >> 16; const height = view.getUint32(heightOffset,false) >> 16; if (width>0 && height>0) return { width, height }; }
      }
      if (size <=0 || offset + size > view.byteLength) break; offset += size;
    }
    return null;
  }
  function parseWebMDimensions(view) {
    let offset = 0, width = 0, height=0; while (offset < Math.min(view.byteLength-8, 32768)) {
      const id = view.getUint8(offset); if (id === 0xB0 && offset+3 < view.byteLength) { const size = view.getUint8(offset+1); if (size<=4 && offset+2+size <= view.byteLength) { width=0; for (let i=0;i<size;i++) width = (width<<8) | view.getUint8(offset+2+i); } }
      if (id === 0xBA && offset+3 < view.byteLength) { const size = view.getUint8(offset+1); if (size<=4 && offset+2+size <= view.byteLength) { height=0; for (let i=0;i<size;i++) height = (height<<8) | view.getUint8(offset+2+i); } }
      if (width>0 && height>0) return { width, height }; offset++;
    }
    return null;
  }
  function buildValidationHeaders(stream) {
    const headers = {}; const ua = stream.headers['User-Agent'] || stream.headers['user-agent']; const ref = stream.headers['Referer'] || stream.headers['referer']; if (ua) headers['User-Agent']=ua; if (ref) headers['Referer']=ref; return headers;
  }
})();
