#!/usr/bin/env python3
"""
Quick Test Script - Demonstrates the new audio merge features
"""

import sys
from pathlib import Path

print("""
================================================================================
🎬 HOTSTAR DOWNLOADER - AUDIO MERGE & CONTINUOUS TESTING
================================================================================

NEW FEATURES ADDED:
==================

1. ✅ Separate Audio/Video Download & Merge
   - Downloads video and audio streams independently
   - Merges with perfect synchronization
   - Supports multiple audio languages
   
2. ✅ Built-in Validation After Every Download
   - Audio/video sync check (±2s tolerance)
   - Full corruption detection (complete decode test)
   - Frame continuity verification
   - Audio quality validation
   
3. ✅ Multi-Audio Track Support
   - Automatically detects all available audio tracks
   - Downloads all languages
   - Embeds with proper metadata
   
4. ✅ Comprehensive Testing Framework
   - 5-level validation tests
   - Detailed JSON and text reports
   - Real-time monitoring mode
   
5. ✅ Automatic Re-download on Failure
   - Auto-retries if validation fails
   - Archives failed attempts
   - Continues until perfect download

================================================================================
USAGE EXAMPLES:
================================================================================

Basic Usage (with auto-validation):
-----------------------------------
python hotstar_auto_downloader.py "https://www.hotstar.com/..."

The downloader will now:
  1. Detect M3U8 playlist
  2. Extract video URL and all audio URLs
  3. Download video stream (without audio)
  4. Download all audio streams separately
  5. Merge video + audio with perfect sync
  6. Validate the merged file automatically
  7. Report any issues immediately

Output example:
  📹 Downloading video stream...
  ✅ Video downloaded: 1234.56 MB
  🎵 Downloading audio stream 1/2 (eng)...
  ✅ Audio eng downloaded: 89.12 MB
  🎵 Downloading audio stream 2/2 (hin)...
  ✅ Audio hin downloaded: 87.45 MB
  🔄 Merging video and audio streams...
  ✅ Merge complete: 1410.13 MB
  🔍 Validating merged file...
  ✅ Validation passed!
     Video: h264 1920x1080
     Audio: 2 track(s), aac
     Duration: 2845.50s

-----------------------------------
Manual Validation:
-----------------------------------
python continuous_validator.py downloads/my_video.mp4

Runs 5 comprehensive tests:
  Test 1: Video information extraction
  Test 2: Audio/video sync verification
  Test 3: Corruption detection (full decode)
  Test 4: Frame continuity check
  Test 5: Audio continuity validation

-----------------------------------
Continuous Monitoring:
-----------------------------------
python continuous_validator.py

Watches downloads/ folder and auto-validates new files:
  👁️  Starting continuous validation monitor...
  📁 Watching: downloads
  🔄 Checking every 5 seconds
  
  🆕 New download detected: my_show_ep1.mp4
  🔍 COMPREHENSIVE VALIDATION: my_show_ep1.mp4
  [runs all 5 tests...]
  ✅ ALL TESTS PASSED - Video is PERFECT!

-----------------------------------
Auto-Test & Re-download (RECOMMENDED):
-----------------------------------
python auto_test_redownload.py "https://www.hotstar.com/..." 3

Downloads, validates, and re-downloads until perfect:
  🚀 DOWNLOAD ATTEMPT 1/3
  [download process...]
  ✅ Download completed
  🔍 VALIDATING...
  ❌ VALIDATION FAILED (sync mismatch)
  🔄 Re-downloading...
  
  🚀 DOWNLOAD ATTEMPT 2/3
  [download process...]
  ✅ Download completed
  🔍 VALIDATING...
  ✅ SUCCESS! Download validated perfectly!

================================================================================
TECHNICAL DETAILS:
================================================================================

Audio/Video Merge Process:
1. Parse M3U8 master playlist
2. Extract video variant URL
3. Extract all audio track URLs (with language codes)
4. Download video stream: ffmpeg -i video_url -c:v copy -an video.mp4
5. Download audio streams: ffmpeg -i audio_url -c:a copy -vn audio.m4a
6. Merge with sync flags:
   ffmpeg -i video.mp4 -i audio1.m4a -i audio2.m4a \\
     -map 0:v:0 -map 1:a:0 -map 2:a:0 \\
     -c:v copy -c:a aac -b:a 192k \\
     -async 1 -vsync 2 \\
     -avoid_negative_ts make_zero \\
     -fflags +genpts+igndts \\
     -metadata:s:a:0 language=eng \\
     -metadata:s:a:1 language=hin \\
     output.mp4

Sync Flags:
  -async 1          : Audio sync method (stretch/squeeze to match video)
  -vsync 2          : Video sync method (passthrough timestamps)
  -avoid_negative_ts: Fix negative timestamp issues
  -fflags +genpts   : Regenerate presentation timestamps
  -fflags +igndts   : Ignore decode timestamps (for discontinuities)

Validation Tests:
  1. Video Info    : Can file be parsed? Valid format?
  2. Sync Check    : Audio duration ≈ Video duration (±2s)
  3. Corruption    : Full decode without errors
  4. Frame Count   : Actual frames ≈ Expected frames (±5%)
  5. Audio Quality : Proper codec, sample rate, channels

================================================================================
FILES CREATED:
================================================================================

1. hotstar_auto_downloader.py (UPDATED)
   - parse_master_playlist(): Now extracts audio URLs
   - download_with_ffmpeg(): Downloads video/audio separately, merges
   - validate_merged_file(): Built-in validation
   - auto_download(): Passes audio URLs to downloader

2. continuous_validator.py (NEW)
   - Comprehensive 5-test validation framework
   - JSON and text report generation
   - Continuous monitoring mode
   - Real-time validation of new downloads

3. auto_test_redownload.py (NEW)
   - Orchestrates download → validate → retry cycle
   - Archives failed attempts
   - Detailed progress reporting
   - Exit codes for CI/CD integration

4. AUDIO_MERGE_TESTING_GUIDE.md (NEW)
   - Complete documentation
   - Usage examples
   - Troubleshooting guide
   - Technical deep-dive

================================================================================
WHAT'S FIXED:
================================================================================

✅ Audio sync issues          : Separate download + sync flags
✅ Missing audio               : Multi-track detection and download
✅ Video corruption            : Full decode validation
✅ Missing segments            : HLS discontinuity handling
✅ Incomplete downloads        : Automatic re-download on failure
✅ No quality verification     : 5-level comprehensive testing
✅ Manual verification needed  : Automated validation after every download

================================================================================
NEXT STEPS:
================================================================================

1. Test with a real Hotstar URL:
   python auto_test_redownload.py "YOUR_HOTSTAR_URL" 3

2. Monitor the output for:
   - Separate video/audio downloads
   - Merge process
   - Validation results

3. Check validation reports in validation_reports/

4. If any issues, the script will automatically retry!

================================================================================
""")

# Check if ffmpeg is available
import subprocess

print("🔍 Checking prerequisites...\n")

try:
    result = subprocess.run(['ffmpeg', '-version'], 
                          capture_output=True, 
                          text=True)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"✅ FFmpeg found: {version_line}")
    else:
        print("❌ FFmpeg not working properly")
except FileNotFoundError:
    print("❌ FFmpeg not found!")
    print("   Install: choco install ffmpeg")

try:
    result = subprocess.run(['ffprobe', '-version'], 
                          capture_output=True, 
                          text=True)
    if result.returncode == 0:
        print("✅ FFprobe found")
    else:
        print("❌ FFprobe not working properly")
except FileNotFoundError:
    print("❌ FFprobe not found!")

print()

# Check if downloads directory exists
downloads_dir = Path("downloads")
if downloads_dir.exists():
    mp4_count = len(list(downloads_dir.glob("*.mp4")))
    print(f"✅ Downloads directory exists ({mp4_count} MP4 files)")
else:
    print("📁 Downloads directory will be created on first download")

# Check if validation reports directory exists
reports_dir = Path("validation_reports")
if reports_dir.exists():
    report_count = len(list(reports_dir.glob("*.json")))
    print(f"✅ Validation reports directory exists ({report_count} reports)")
else:
    print("📁 Validation reports directory will be created on first validation")

print("\n" + "="*80)
print("🚀 READY TO GO!")
print("="*80)
print("\nTry one of the usage examples above to get started!")
print("\nFor full documentation, see: AUDIO_MERGE_TESTING_GUIDE.md")
print("="*80 + "\n")
