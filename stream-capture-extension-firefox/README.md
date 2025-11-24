# Universal Stream Capture (Firefox Port)

This is the Firefox-adapted version of the original Chrome MV3 extension.

## Key Differences From Chrome Version
- Uses Manifest V2 (Firefox MV3 service workers still partial).
- Persistent background script (`background.js`) instead of service worker.
- `browser_action` replaces `action`.
- Added `browser_specific_settings.gecko` with extension ID `stream-capture@example.com`.
- Polyfilled APIs using `const api = browser || chrome` pattern.
- `webRequestBlocking` permission included for future header modifications.

## Features
- Capture M3U8, MPD, MP4, WebM, MKV, TS, M4S requests.
- Detect DRM/license endpoints (Widevine, PlayReady, FairPlay keywords).
- Resolution detection for master playlists (M3U8 `#EXT-X-STREAM-INF`, MPD `<Representation>` tags).
- Embedded link extraction from fetch/XHR response bodies (nested playlists/media paths).
- Advanced optional in-page hooks (fetch/XHR/video src/DRM) gated by toggle.
- Throttled validation queue to avoid network hammering.
- Persistent storage of captured streams per tab.

## Install (Temporary)
1. Open `about:debugging` in Firefox.
2. Click "This Firefox".
3. Click "Load Temporary Add-on".
4. Select this folder and choose `manifest.json`.
5. Open a video site, then click the extension icon to view captured streams.

## Recommended Test Pages
- YouTube video watch page.
- HLS test streams (e.g. https://test-streams.mux.dev/). 
- DASH test streams (e.g. https://dash.akamaized.net/). 

## Advanced Capture Toggle
Turn it on if you need deeper embedded URL extraction (nested manifests inside JSON or license responses). Leave off for minimal footprint.

## Exporting
Use the Export button in popup to download JSON of current tab's streams.

## Caveats
- DRM-protected media cannot be directly downloaded; license endpoints are flagged for reference only.
- Segment URLs are not yet grouped; volume-heavy segment lists may appear.
- Manifest V2 deprecation in Chrome does not affect Firefox; this port is Firefox-specific.

## Next Enhancements
- Segment grouping & variant hierarchy view.
- Parent-child mapping display (master → variants → segments).
- Optional ffmpeg command generation with headers for MPD manifests.

## Troubleshooting
If no items appear:
- Ensure page actually started playback.
- Toggle Advanced ON to catch XHR/fetch based manifests.
- Check console (Browser Console) for extension errors.

---
MIT-style usage allowed; avoid capturing or redistributing copyrighted streams without permission.
