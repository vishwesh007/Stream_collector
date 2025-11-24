#!/usr/bin/env python3
"""
Hotstar Auto Downloader with Playwright
Monitors network traffic, detects M3U8 playlists, injects download UI
"""

import asyncio
import json
import re
import subprocess
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, Route, Response
from urllib.parse import urljoin, urlparse
import urllib.request
import zipfile

class HotstarDownloader:
    def __init__(self, downloads_dir="downloads"):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(exist_ok=True)
        self.captured_playlists = []
        self.headers = {}
        self.cookies = {}
        self.page_url = ""
        self.profile_dir = Path(tempfile.gettempdir()) / "hotstar_firefox_profile"
        self.extensions_dir = Path("browser_extensions")
        self.extensions_dir.mkdir(exist_ok=True)
    
    def download_ublock_extension(self):
        """Download uBlock Origin XPI for Firefox"""
        ublock_xpi = self.extensions_dir / "ublock_origin.xpi"
        
        if ublock_xpi.exists():
            print("✅ uBlock Origin already downloaded")
            return str(ublock_xpi)
        
        print("📥 Downloading uBlock Origin extension...")
        
        # uBlock Origin direct XPI download
        ublock_url = "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi"
        
        try:
            urllib.request.urlretrieve(ublock_url, ublock_xpi)
            print(f"✅ Downloaded uBlock Origin to: {ublock_xpi}")
            return str(ublock_xpi)
        except Exception as e:
            print(f"⚠️  Failed to download extension: {e}")
            return None
    
    def setup_firefox_profile_with_extension(self, extension_path):
        """Create a Firefox profile and install extension"""
        if not extension_path or not Path(extension_path).exists():
            print("⚠️  No extension to install")
            return None
        
        # Create profile directory
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Create extensions directory in profile
        extensions_profile_dir = self.profile_dir / "extensions"
        extensions_profile_dir.mkdir(exist_ok=True)
        
        # Copy extension to profile extensions directory
        # Firefox expects extensions with their ID as filename
        extension_dest = extensions_profile_dir / "uBlock0@raymondhill.net.xpi"
        shutil.copy2(extension_path, extension_dest)
        
        print(f"✅ Installed uBlock Origin to Firefox profile: {self.profile_dir}")
        return str(self.profile_dir)
    
    async def monitor_network(self, response: Response):
        """Monitor all network responses for M3U8 playlists"""
        try:
            url = response.url
            content_type = response.headers.get('content-type', '')
            
            # Detect M3U8 playlist responses
            if ('.m3u8' in url or 'mpegurl' in content_type.lower()):
                try:
                    body = await response.text()
                    
                    # Check if it's a master playlist with quality variants
                    if '#EXTM3U' in body:
                        print(f"\n🎯 Detected M3U8 playlist: {url[:100]}...")
                        
                        # Save playlist content to file
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        playlist_file = self.downloads_dir / f"playlist_{timestamp}.m3u8"
                        playlist_file.write_text(body, encoding='utf-8')
                        print(f"💾 Saved playlist to: {playlist_file}")
                        
                        # Extract headers and cookies from the request
                        request = response.request
                        self.headers = dict(request.headers)
                        
                        # Create HAR file
                        har_data = self.create_har_from_request(request, response, body)
                        har_file = self.downloads_dir / f"playlist_{timestamp}.har"
                        har_file.write_text(json.dumps(har_data, indent=2), encoding='utf-8')
                        print(f"💾 Saved HAR to: {har_file}")
                        
                        # Parse variants if it's a master playlist
                        variants = []
                        if '#EXT-X-STREAM-INF' in body:
                            variants = self.parse_master_playlist(body, url)
                            print(f"✅ Found {len(variants)} quality variants")
                            for v in variants[:3]:  # Show first 3
                                print(f"   • {v['resolution']} @ {v['bandwidth']/1_000_000:.1f} Mbps")
                            if len(variants) > 3:
                                print(f"   ... and {len(variants)-3} more")
                        else:
                            # Single variant playlist
                            variants = [{'url': url, 'resolution': 'auto', 'bandwidth': 0}]
                            print(f"✅ Found single variant playlist")
                        
                        # Save all info
                        playlist_info = {
                            'url': url,
                            'base_url': url.rsplit('/', 1)[0] + '/',
                            'variants': variants,
                            'body': body,
                            'timestamp': timestamp,
                            'headers': self.headers,
                            'page_url': self.page_url,
                            'playlist_file': str(playlist_file),
                            'har_file': str(har_file)
                        }
                        
                        self.captured_playlists.append(playlist_info)
                        
                        # Auto-download the best quality
                        if variants:
                            best_variant = max(variants, key=lambda x: x['bandwidth'])
                            print(f"\n🚀 Auto-downloading best quality: {best_variant.get('resolution', 'auto')}")
                            
                            # Get page title for filename
                            page_title = await self.page.title() if hasattr(self, 'page') and self.page else ""
                            
                            await self.auto_download(best_variant, self.headers, timestamp, url, page_title)
                                
                except Exception as e:
                    print(f"⚠️  Error processing response: {e}")
                    
        except Exception as e:
            pass  # Ignore errors for non-text responses
    
    def create_har_from_request(self, request, response, body):
        """Create HAR format data from request/response"""
        return {
            "log": {
                "version": "1.2",
                "creator": {"name": "HotstarDownloader", "version": "1.0"},
                "entries": [
                    {
                        "startedDateTime": datetime.now().isoformat(),
                        "request": {
                            "method": request.method,
                            "url": request.url,
                            "headers": [{"name": k, "value": v} for k, v in request.headers.items()],
                            "cookies": []
                        },
                        "response": {
                            "status": response.status,
                            "statusText": response.status_text,
                            "headers": [{"name": k, "value": v} for k, v in response.headers.items()],
                            "cookies": [],
                            "content": {
                                "size": len(body),
                                "mimeType": response.headers.get('content-type', 'application/vnd.apple.mpegurl'),
                                "text": body
                            }
                        }
                    }
                ]
            }
        }
    
    def parse_master_playlist(self, content, base_url):
        """Parse M3U8 master playlist and extract quality variants"""
        variants = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF:'):
                # Parse attributes
                bandwidth = re.search(r'BANDWIDTH=(\d+)', line)
                resolution = re.search(r'RESOLUTION=(\d+x\d+)', line)
                codecs = re.search(r'CODECS="([^"]+)"', line)
                frame_rate = re.search(r'FRAME-RATE=([\d.]+)', line)
                
                # Next line should be the variant URL
                if i + 1 < len(lines):
                    variant_url = lines[i + 1].strip()
                    if variant_url and not variant_url.startswith('#'):
                        # Make absolute URL
                        if not variant_url.startswith('http'):
                            variant_url = urljoin(base_url, variant_url)
                        
                        variants.append({
                            'url': variant_url,
                            'bandwidth': int(bandwidth.group(1)) if bandwidth else 0,
                            'resolution': resolution.group(1) if resolution else 'unknown',
                            'codecs': codecs.group(1) if codecs else 'unknown',
                            'frame_rate': float(frame_rate.group(1)) if frame_rate else 25.0
                        })
        
        # Sort by bandwidth (quality)
        variants.sort(key=lambda x: x['bandwidth'], reverse=True)
        return variants
    
    async def inject_download_ui(self, playlist_info):
        """Inject download UI into the webpage"""
        if not hasattr(self, 'page') or not self.page:
            return
        
        variants = playlist_info['variants']
        
        # Create quality options HTML
        quality_options = []
        for i, v in enumerate(variants):
            bw_mbps = v['bandwidth'] / 1_000_000
            quality_options.append(f"""
                <option value="{i}" data-url="{v['url']}" data-resolution="{v['resolution']}">
                    {v['resolution']} - {bw_mbps:.1f} Mbps ({v['codecs']})
                </option>
            """)
        
        # JavaScript code to handle downloads
        download_handler_js = """
        window.hotstarDownloader = {
            playlistInfo: %s,
            
            async download() {
                const select = document.getElementById('hsd-quality-select');
                const btn = document.getElementById('hsd-download-btn');
                const status = document.getElementById('hsd-status');
                const progress = document.getElementById('hsd-progress');
                
                const selectedIndex = parseInt(select.value);
                const variant = this.playlistInfo.variants[selectedIndex];
                
                btn.disabled = true;
                btn.textContent = '⏳ Starting...';
                status.textContent = 'Preparing download...';
                status.style.display = 'block';
                progress.style.display = 'block';
                
                try {
                    // Call Python backend to download
                    const response = await fetch('http://localhost:8765/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            variant: variant,
                            headers: this.playlistInfo.headers,
                            page_url: this.playlistInfo.page_url
                        })
                    });
                    
                    if (!response.ok) throw new Error('Download failed');
                    
                    const result = await response.json();
                    status.textContent = '✅ ' + result.message;
                    btn.textContent = '✅ Downloaded';
                    
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.textContent = '⬇️ Download';
                        status.style.display = 'none';
                        progress.style.display = 'none';
                    }, 3000);
                    
                } catch (error) {
                    status.textContent = '❌ Error: ' + error.message;
                    btn.disabled = false;
                    btn.textContent = '⬇️ Download';
                    console.error('Download error:', error);
                }
            }
        };
        """ % json.dumps(playlist_info)
        
        # CSS and HTML for the UI
        ui_html = f"""
        <div id="hotstar-downloader-ui" style="
            position: fixed;
            top: 10px;
            left: 10px;
            z-index: 999999;
            background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            min-width: 320px;
            color: white;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 16px; font-weight: 600;">📥 Video Downloader</h3>
                <button onclick="document.getElementById('hotstar-downloader-ui').style.display='none'" 
                    style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; 
                    border-radius: 4px; cursor: pointer; font-size: 14px;">✕</button>
            </div>
            
            <select id="hsd-quality-select" style="
                width: 100%%;
                padding: 8px 12px;
                border-radius: 6px;
                border: 2px solid rgba(255,255,255,0.3);
                background: rgba(255,255,255,0.1);
                color: white;
                font-size: 13px;
                margin-bottom: 10px;
                cursor: pointer;
            ">
                {''.join(quality_options)}
            </select>
            
            <button id="hsd-download-btn" onclick="window.hotstarDownloader.download()" style="
                width: 100%%;
                padding: 10px;
                background: #48bb78;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
            " onmouseover="this.style.background='#38a169'" 
               onmouseout="this.style.background='#48bb78'">
                ⬇️ Download
            </button>
            
            <div id="hsd-status" style="
                margin-top: 10px;
                padding: 8px;
                background: rgba(255,255,255,0.1);
                border-radius: 6px;
                font-size: 12px;
                display: none;
            "></div>
            
            <div id="hsd-progress" style="
                margin-top: 8px;
                height: 4px;
                background: rgba(255,255,255,0.2);
                border-radius: 2px;
                overflow: hidden;
                display: none;
            ">
                <div style="
                    height: 100%%;
                    background: #48bb78;
                    animation: progress 2s ease-in-out infinite;
                "></div>
            </div>
            
            <style>
                @keyframes progress {{
                    0%% {{ width: 0%%; }}
                    50%% {{ width: 70%%; }}
                    100%% {{ width: 100%%; }}
                }}
            </style>
        </div>
        """
        
        try:
            # Inject the UI and handler
            await self.page.evaluate(download_handler_js)
            await self.page.evaluate(f"document.body.insertAdjacentHTML('beforeend', `{ui_html}`)")
            print("✅ Download UI injected into page")
        except Exception as e:
            print(f"⚠️  Failed to inject UI: {e}")
    
    async def start_download_server(self):
        """Start HTTP server to handle download requests from browser"""
        from aiohttp import web
        
        async def handle_download(request):
            try:
                data = await request.json()
                variant = data['variant']
                headers = data['headers']
                page_url = data.get('page_url', '')
                
                # Generate filename
                filename = self.generate_filename(variant['url'], page_url)
                output_path = self.downloads_dir / filename
                
                print(f"\n🚀 Starting download: {variant['resolution']} @ {variant['bandwidth']/1_000_000:.1f} Mbps")
                print(f"📁 Output: {output_path}")
                
                # Download using ffmpeg
                success = await self.download_with_ffmpeg(variant['url'], headers, output_path)
                
                if success:
                    return web.json_response({
                        'success': True,
                        'message': f'Downloaded to {output_path.name}',
                        'path': str(output_path)
                    })
                else:
                    return web.json_response({
                        'success': False,
                        'message': 'Download failed - check console'
                    }, status=500)
                    
            except Exception as e:
                print(f"❌ Download error: {e}")
                return web.json_response({
                    'success': False,
                    'message': str(e)
                }, status=500)
        
        app = web.Application()
        app.router.add_post('/download', handle_download)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8765)
        await site.start()
        print("✅ Download server started on http://localhost:8765")
        
        return runner
    
    def generate_filename(self, url, page_url):
        """Generate clean filename from URL - remove domain and numbers"""
        if page_url and 'hotstar.com' in page_url:
            # Extract from page URL
            parsed = urlparse(page_url)
            segments = [s for s in parsed.path.split('/') if s]
            clean = []
            for seg in segments:
                # Remove segments that are purely numeric or in exclusion list
                if not re.match(r'^\d+$', seg) and seg.lower() not in ['in', 'shows', 'movies', 'watch']:
                    # Remove any trailing/leading numbers from the segment
                    cleaned_seg = re.sub(r'^\d+[-_]?|[-_]?\d+$', '', seg)
                    if cleaned_seg:
                        clean.append(cleaned_seg)
            if clean:
                name = '_'.join(clean)  # Use all meaningful parts
                # Replace hyphens with underscores for consistency
                name = name.replace('-', '_')
                return f"{name}.mp4"
        
        # Fallback to timestamp
        return f"hotstar_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    
    async def auto_download(self, variant, headers, timestamp, playlist_url, page_title=""):
        """Automatically download using ffmpeg"""
        # Generate filename from the page title (from browser tab/title bar)
        if page_title:
            # Clean the page title - remove common suffixes and clean special chars
            title_clean = page_title
            
            # Remove common streaming site suffixes
            for suffix in [' - Disney+ Hotstar', ' | Disney+ Hotstar', ' - Hotstar', ' | Hotstar', 
                          ' - Watch Online', ' | Watch Online', ' - Stream', ' | Stream']:
                title_clean = title_clean.replace(suffix, '')
            
            # Remove special characters and clean up
            title_clean = re.sub(r'[^\w\s-]', '', title_clean)  # Keep alphanumeric, spaces, hyphens
            title_clean = re.sub(r'\s+', '_', title_clean.strip())  # Replace spaces with underscores
            title_clean = re.sub(r'_+', '_', title_clean)  # Remove multiple underscores
            title_clean = title_clean.strip('_')  # Remove leading/trailing underscores
            
            if title_clean and len(title_clean) > 3:
                filename = f"{title_clean}_{timestamp}.mp4"
            else:
                filename = f"hotstar_{timestamp}.mp4"
        else:
            # Fallback to extracting from M3U8 URL path
            parsed = urlparse(playlist_url)
            url_path = parsed.path
            
            segments = [s for s in url_path.split('/') if s]
            clean = []
            
            for seg in segments:
                seg_clean = seg.replace('.m3u8', '').replace('.mpd', '')
                if seg_clean and not re.match(r'^\d+$', seg_clean):
                    seg_clean = re.sub(r'^\d+[-_]?|[-_]?\d+$', '', seg_clean)
                    if seg_clean and len(seg_clean) > 2:
                        clean.append(seg_clean)
            
            if clean:
                filename = f"{'_'.join(clean[-3:]).replace('-', '_')}_{timestamp}.mp4"
            else:
                filename = f"hotstar_{timestamp}.mp4"
        
        output_path = self.downloads_dir / filename
        
        print(f"📁 Output: {output_path}")
        print(f"📎 Source: {playlist_url[:80]}...")
        if page_title:
            print(f"📺 Title: {page_title}")
        await self.download_with_ffmpeg(variant['url'], headers, output_path)
    
    async def download_with_ffmpeg(self, variant_url, headers, output_path):
        """Download video using ffmpeg"""
        # Build headers string for ffmpeg
        header_list = []
        for key, value in headers.items():
            if key.lower() not in ['host', 'content-length', 'connection']:
                header_list.append(f'{key}: {value}')
        
        headers_str = '\r\n'.join(header_list) + '\r\n'
        
        # FFmpeg command
        cmd = [
            'ffmpeg',
            '-loglevel', 'info',
            '-headers', headers_str,
            '-i', variant_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',
            str(output_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                size_mb = output_path.stat().st_size / (1024*1024)
                print(f"✅ Download complete: {size_mb:.2f} MB")
                return True
            else:
                print(f"❌ FFmpeg failed with code {process.returncode}")
                print(stderr.decode()[-500:])  # Last 500 chars
                return False
                
        except FileNotFoundError:
            print("❌ ffmpeg not found! Install it:")
            print("   Windows: choco install ffmpeg")
            print("   Mac: brew install ffmpeg")
            print("   Linux: apt install ffmpeg")
            return False
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False
    
    async def run(self, url, headless=False):
        """Main entry point - open browser and monitor"""
        async with async_playwright() as p:
            print("🚀 Starting Hotstar Auto Downloader...")
            print(f"📺 Target URL: {url}")
            
            # Download and install uBlock Origin extension
            extension_path = self.download_ublock_extension()
            profile_path = self.setup_firefox_profile_with_extension(extension_path)
            
            # Start download server
            runner = await self.start_download_server()
            
            try:
                # Browser preferences
                firefox_prefs = {
                    # Enable DRM/Widevine
                    'media.eme.enabled': True,
                    'media.gmp-widevinecdm.enabled': True,
                    'media.gmp-widevinecdm.visible': True,
                    'media.gmp-manager.updateEnabled': True,
                    # Additional media settings
                    'media.autoplay.default': 0,
                    'media.autoplay.blocking_policy': 0,
                    # Enhanced ad blocking settings
                    'privacy.trackingprotection.enabled': True,
                    'privacy.trackingprotection.pbmode.enabled': True,
                    'privacy.trackingprotection.socialtracking.enabled': True,
                    'privacy.trackingprotection.cryptomining.enabled': True,
                    'privacy.trackingprotection.fingerprinting.enabled': True,
                    'browser.contentblocking.category': 'strict',
                    'privacy.annotate_channels.strict_list.enabled': True,
                    # Extension support
                    'xpinstall.signatures.required': False,
                    'extensions.autoDisableScopes': 0,
                    'extensions.enabledScopes': 15,
                }
                
                # Launch browser with persistent context (required for extensions)
                if profile_path:
                    context = await p.firefox.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        headless=headless,
                        firefox_user_prefs=firefox_prefs,
                        device_scale_factor=3,
                        has_touch=True,
                        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                        args=['--start-maximized']
                    )
                    print("✅ Firefox launched with uBlock Origin extension")
                    print("✅ Enhanced ad blocking enabled (Firefox Tracking Protection + uBlock Origin)")
                else:
                    # Fallback without profile
                    browser = await p.firefox.launch(
                        headless=headless,
                        firefox_user_prefs=firefox_prefs,
                        args=['--start-maximized']
                    )
                    context = await browser.new_context(
                        device_scale_factor=3,
                        has_touch=True,
                        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
                    )
                    print("✅ Firefox launched (without extension)")
                
                self.page = await context.new_page()
                self.page_url = url
                
                # Inject aggressive ad blocker script
                await self.page.add_init_script("""
                    // Block common ad domains and trackers
                    const adDomains = [
                        'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
                        'amazon-adsystem.com', 'advertising.com', 'adbrite.com',
                        'adnxs.com', 'adsrvr.org', 'criteo.com', 'outbrain.com',
                        'taboola.com', 'smartadserver.com', 'pubmatic.com'
                    ];
                    
                    // Override fetch and XMLHttpRequest to block ad requests
                    const originalFetch = window.fetch;
                    window.fetch = function(...args) {
                        const url = args[0];
                        if (typeof url === 'string' && adDomains.some(domain => url.includes(domain))) {
                            console.log('🚫 Blocked ad request:', url);
                            return Promise.reject(new Error('Ad blocked'));
                        }
                        return originalFetch.apply(this, args);
                    };
                    
                    const originalOpen = XMLHttpRequest.prototype.open;
                    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                        if (adDomains.some(domain => url.includes(domain))) {
                            console.log('🚫 Blocked XHR ad request:', url);
                            return;
                        }
                        return originalOpen.call(this, method, url, ...rest);
                    };
                    
                    // Remove ad elements from DOM
                    function removeAds() {
                        const adSelectors = [
                            '[class*="ad-"]', '[id*="ad-"]', '[class*="advertisement"]',
                            '[id*="advertisement"]', '.ad', '#ad', 'iframe[src*="doubleclick"]',
                            'iframe[src*="googlesyndication"]', '[data-ad-slot]'
                        ];
                        
                        adSelectors.forEach(selector => {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el && el.parentNode) {
                                    el.parentNode.removeChild(el);
                                }
                            });
                        });
                    }
                    
                    // Run ad removal on load and periodically
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', removeAds);
                    } else {
                        removeAds();
                    }
                    setInterval(removeAds, 2000);
                """)
                
                print("✅ JavaScript ad blocker injected")
                
                # Block ad requests at network level
                async def route_handler(route):
                    url = route.request.url
                    ad_patterns = [
                        'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
                        'amazon-adsystem.com', 'advertising.com', 'adbrite.com',
                        'adnxs.com', 'adsrvr.org', 'criteo.com', 'outbrain.com',
                        'taboola.com', 'smartadserver.com', 'pubmatic.com',
                        '/ads/', '/advertisement/', '/tracking/', '/analytics/'
                    ]
                    
                    if any(pattern in url for pattern in ad_patterns):
                        print(f"🚫 Blocked: {url[:80]}...")
                        await route.abort()
                    else:
                        await route.continue_()
                
                await self.page.route('**/*', route_handler)
                print("✅ Network-level ad blocking enabled")
                
                # Set up network monitoring
                self.page.on('response', lambda response: asyncio.create_task(self.monitor_network(response)))
                
                # Navigate to page
                print(f"\n🌐 Opening {url}...")
                await self.page.goto(url, wait_until='domcontentloaded')
                
                print("\n👀 Monitoring network traffic for M3U8 playlists...")
                print("   Play the video to detect the playlist")
                print("   Press Ctrl+C to exit\n")
                
                # Keep browser open and monitor
                while True:
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping...")
            finally:
                try:
                    await runner.cleanup()
                except:
                    pass
                try:
                    await context.close()
                except:
                    pass


async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hotstar_auto_downloader.py <hotstar_url> [--headless]")
        print("\nExample:")
        print('  python hotstar_auto_downloader.py "https://www.hotstar.com/in/shows/..." ')
        print('  python hotstar_auto_downloader.py "https://www.hotstar.com/in/shows/..." --headless')
        print("\nFeatures:")
        print("  • Automatically detects M3U8 master playlists")
        print("  • Injects download UI into webpage (top-left corner)")
        print("  • Select quality and click Download")
        print("  • Downloads with ffmpeg, preserves quality")
        sys.exit(1)
    
    url = sys.argv[1]
    headless = '--headless' in sys.argv
    
    downloader = HotstarDownloader(downloads_dir='downloads')
    await downloader.run(url, headless=headless)


if __name__ == '__main__':
    asyncio.run(main())
