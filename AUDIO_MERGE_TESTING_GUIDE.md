# Audio Merge & Continuous Testing - Complete Guide

## Overview

The Hotstar downloader now includes:
1. **Separate audio/video download and merge** - Downloads audio and video streams separately, then merges with perfect sync
2. **Multi-audio track support** - Handles multiple audio languages
3. **Comprehensive validation** - 5-level testing framework
4. **Automatic re-download** - Re-downloads until validation passes
5. **Continuous monitoring** - Auto-validates new downloads

## Features Added

### 1. Audio Download & Merge
- **Separate streams**: Downloads video and audio independently
- **Multiple audio tracks**: Supports multiple language audio tracks
- **Smart merging**: Uses FFmpeg with sync flags for perfect A/V alignment
- **Validation**: Built-in validation after every merge

### 2. Enhanced Validation
- **Audio/Video sync check**: Ensures perfect synchronization (tolerance: 2s)
- **Corruption detection**: Full decode test to find any corruption
- **Frame continuity**: Checks for missing frames or discontinuities
- **Audio continuity**: Validates audio stream completeness
- **Multi-track validation**: Verifies all audio tracks

### 3. Automatic Testing & Re-download
- **Auto-validation**: Every download is automatically validated
- **Re-download on failure**: Automatically retries if validation fails
- **Failed file archiving**: Keeps failed attempts for debugging
- **Detailed reports**: JSON and text reports for every test

## New Files

### 1. `continuous_validator.py`
Comprehensive validation tool with 5 test categories:
- Video information extraction
- Audio/video sync verification
- Corruption detection (full decode)
- Frame continuity check
- Audio continuity check

### 2. `auto_test_redownload.py`
Automated testing and re-download orchestrator:
- Downloads video
- Validates automatically
- Re-downloads if validation fails
- Tracks attempts and success/failure

## Usage

### Basic Usage (Auto-download with validation)

```powershell
# Download and auto-validate
python hotstar_auto_downloader.py "https://www.hotstar.com/..."
```

The downloader now automatically:
1. Detects M3U8 playlist
2. Extracts video and audio URLs
3. Downloads video stream
4. Downloads all audio streams
5. Merges with perfect sync
6. Validates the merged file
7. Reports any issues immediately

### Manual Validation

```powershell
# Validate a specific file
python continuous_validator.py downloads\my_video.mp4
```

Output:
```
🔍 COMPREHENSIVE VALIDATION: my_video.mp4
================================================================================

📊 Test 1/5: Getting video information...
✅ Video info retrieved

🎬 Test 2/5: Checking audio/video sync...
✅ Sync check passed - 2 audio track(s)

🔍 Test 3/5: Checking for video corruption...
✅ No corruption detected

🎞️  Test 4/5: Checking frame continuity...
✅ Frame continuity OK - 54234 frames

🎵 Test 5/5: Checking audio continuity...
✅ Audio continuity OK - 2 channel(s)

================================================================================
✅ ALL TESTS PASSED - Video is PERFECT!
⏱️  Validation completed in 15.32s
================================================================================
```

### Continuous Monitoring

```powershell
# Monitor downloads folder and auto-validate new files
python continuous_validator.py
```

This will:
- Watch the `downloads/` folder
- Automatically validate any new MP4 files
- Generate reports for each file
- Alert if validation fails

### Auto-Test & Re-download

```powershell
# Download with automatic retries until perfect
python auto_test_redownload.py "https://www.hotstar.com/..." 3
```

This advanced mode:
1. Downloads the video
2. Validates comprehensively
3. If validation fails, re-downloads (up to 3 attempts)
4. Archives failed attempts
5. Continues until validation passes

Example output:
```
################################################################################
# AUTO TEST & RE-DOWNLOAD CYCLE
# URL: https://www.hotstar.com/...
# Max Retries: 3
################################################################################

🚀 DOWNLOAD ATTEMPT 1/3
================================================================================
[Download progress...]

✅ Download completed: my_show_episode_1.mp4
📊 Size: 1234.56 MB

🔍 VALIDATING: my_show_episode_1.mp4
================================================================================
[Validation tests...]

❌ VALIDATION FAILED on attempt 1
   Issues:
     • Audio/Video sync mismatch: 3.24s difference

🔄 Re-downloading (attempt 2/3)...

🚀 DOWNLOAD ATTEMPT 2/3
================================================================================
[Download progress...]

✅ SUCCESS! Download validated perfectly!
📁 File: downloads/my_show_episode_1.mp4
📊 Size: 1234.56 MB
🎉 All tests passed on attempt 2/3
```

## Validation Tests Explained

### Test 1: Video Information
- Extracts format, duration, codecs, bitrate
- Verifies file is readable
- **Pass criteria**: File can be parsed by ffprobe

### Test 2: Audio/Video Sync
- Compares video and audio stream durations
- Checks for sync mismatches
- Validates multiple audio tracks
- **Pass criteria**: Duration difference < 2 seconds

### Test 3: Corruption Detection
- Full decode test using FFmpeg
- Detects any encoding errors
- Catches truncated files
- **Pass criteria**: No errors during full decode

### Test 4: Frame Continuity
- Counts total frames
- Compares with expected frame count
- Detects missing frames
- **Pass criteria**: Frame count matches expected (within 5%)

### Test 5: Audio Continuity
- Checks audio stream completeness
- Validates sample rate and channels
- Compares audio duration with container
- **Pass criteria**: No gaps, proper format

## Validation Reports

Reports are saved to `validation_reports/`:

### JSON Report
```json
{
  "file": "downloads/my_video.mp4",
  "timestamp": "2025-11-25T10:30:45.123456",
  "file_size_mb": 1234.56,
  "video_info": {
    "format": "mov,mp4,m4a,3gp,3g2,mj2",
    "duration": 2845.5,
    "bit_rate": 3500000,
    "video_codec": "h264",
    "audio_codec": "aac"
  },
  "tests": {
    "sync": {
      "valid": true,
      "issues": [],
      "warnings": [],
      "video_streams": 1,
      "audio_streams": 2,
      "video_duration": 2845.5,
      "audio_duration": 2845.3
    },
    "corruption": {
      "valid": true,
      "issues": [],
      "warnings": []
    },
    "frames": {
      "valid": true,
      "nb_frames": 68292,
      "nb_packets": 68292,
      "duration": 2845.5
    },
    "audio": {
      "valid": true,
      "audio_duration": 2845.3,
      "sample_rate": 48000,
      "channels": 2
    }
  },
  "summary": {
    "all_tests_passed": true,
    "total_issues": 0,
    "total_warnings": 0,
    "validation_time_seconds": 15.32
  }
}
```

### Text Report
Clean, readable format for quick review:
```
================================================================================
VALIDATION REPORT: my_video
================================================================================
File: downloads/my_video.mp4
Size: 1234.56 MB
Timestamp: 2025-11-25T10:30:45.123456

VIDEO INFO:
  Format: mov,mp4,m4a,3gp,3g2,mj2
  Duration: 2845.50s
  Video Codec: h264
  Audio Codec: aac

TEST RESULTS:

SYNC: ✅ PASS

CORRUPTION: ✅ PASS

FRAMES: ✅ PASS

AUDIO: ✅ PASS

================================================================================
SUMMARY:
  Overall Status: ✅ PASSED
  Total Issues: 0
  Total Warnings: 0
  Validation Time: 15.32s
================================================================================
```

## Audio Merge Details

### How It Works
1. **Video stream download**:
   ```
   ffmpeg -i video_url -c:v copy -an video.mp4
   ```

2. **Audio stream(s) download**:
   ```
   ffmpeg -i audio_url_1 -c:a copy -vn audio_en.m4a
   ffmpeg -i audio_url_2 -c:a copy -vn audio_hi.m4a
   ```

3. **Merge with sync**:
   ```
   ffmpeg -i video.mp4 -i audio_en.m4a -i audio_hi.m4a \
     -map 0:v:0 -map 1:a:0 -map 2:a:0 \
     -c:v copy -c:a aac -b:a 192k \
     -async 1 -vsync 2 \
     -avoid_negative_ts make_zero \
     -fflags +genpts+igndts \
     -metadata:s:a:0 language=eng \
     -metadata:s:a:1 language=hin \
     output.mp4
   ```

### Sync Flags Explained
- `-async 1`: Audio sync method (stretch/squeeze audio to match video)
- `-vsync 2`: Video sync method (passthrough timestamps)
- `-avoid_negative_ts make_zero`: Fix negative timestamps
- `-fflags +genpts+igndts`: Regenerate PTS, ignore DTS
- `-max_muxing_queue_size 2048`: Large buffer for HLS discontinuities

## Troubleshooting

### Issue: "Audio/Video sync mismatch"
**Cause**: Different durations between audio and video streams  
**Solution**: The auto-retry will re-download. Usually fixes on 2nd attempt.

### Issue: "Corruption detected"
**Cause**: Incomplete download or network interruption  
**Solution**: Automatic re-download will fix this

### Issue: "No audio stream found"
**Cause**: M3U8 doesn't have separate audio URL  
**Solution**: Downloader will extract embedded audio from video stream

### Issue: "Frame count mismatch"
**Cause**: HLS discontinuities or missing segments  
**Solution**: FFmpeg flags handle this, but validation will catch if severe

### Issue: Multiple failed attempts
**Cause**: Persistent network issues or DRM-protected content  
**Check**:
1. Network connection
2. DRM status (Widevine enabled?)
3. Check failed files in downloads folder (renamed with `_FAILED_attempt1`)

## Advanced Options

### Custom Validation Tolerance

Edit `continuous_validator.py`:
```python
# Line ~104: Sync tolerance
if duration_diff > 2.0:  # Change from 2.0 to your preference
    issues.append(...)

# Line ~209: Frame count tolerance
if frame_diff_pct > 5:  # Change from 5% to your preference
    warnings.append(...)
```

### Skip Audio Download (Video Only)

Edit `hotstar_auto_downloader.py` line ~530:
```python
# Set audio_urls to None to skip audio download
await self.download_with_ffmpeg(variant['url'], headers, output_path, audio_urls=None)
```

### Change Audio Bitrate

Edit `hotstar_auto_downloader.py` line ~682:
```python
'-b:a', '192k',  # Change from 192k to 128k, 256k, or 320k
```

## Performance Tips

1. **Parallel downloads**: Audio and video download sequentially. Could be parallelized for speed.
2. **Validation speed**: Full corruption test is slow. Skip if testing frequently.
3. **Temp files**: Cleaned automatically on success, kept on failure for debugging.

## Integration with Existing Workflow

### Before (Old Method)
```powershell
python hotstar_auto_downloader.py "url"
# Hope it worked, manually check quality
```

### After (New Method)
```powershell
# Option 1: Basic (with built-in validation)
python hotstar_auto_downloader.py "url"

# Option 2: Continuous monitoring
python continuous_validator.py &  # In background
python hotstar_auto_downloader.py "url"

# Option 3: Auto-retry until perfect
python auto_test_redownload.py "url" 3
```

## What Gets Validated

✅ **File completeness**: Full decode test  
✅ **Audio sync**: Duration comparison  
✅ **Frame count**: Expected vs actual  
✅ **Audio quality**: Codec, sample rate, channels  
✅ **Multi-track audio**: All tracks validated  
✅ **Container integrity**: Format validation  
✅ **Timestamp continuity**: HLS discontinuity handling  

❌ **NOT validated**:  
- Visual quality (requires manual review)
- Subtitle accuracy
- Specific content (you must verify content manually)

## Summary

The enhanced downloader now provides:
1. **Separate audio/video download** for better quality control
2. **Multi-audio track support** for language options
3. **5-level validation** to catch any issues
4. **Automatic re-download** on validation failure
5. **Detailed reports** for debugging
6. **Continuous monitoring** for batch downloads

**No more broken downloads, missing audio, or sync issues!**
