# Video Download Testing Plan

## Overview
Comprehensive automated testing framework to validate downloaded MP4 files from Hotstar Auto Downloader for correctness, integrity, and completeness.

## Test Categories

### 1. File Integrity Tests
- **File Existence**: Verify file was created successfully
- **File Size**: Ensure file size is > 0 bytes and reasonable for video content
- **File Hash**: Calculate SHA-256 hash for integrity verification and future comparison
- **Read Permissions**: Verify file is readable and not corrupted at filesystem level

### 2. Video Stream Validation
- **Stream Presence**: Verify video stream exists
- **Video Codec**: Validate codec is supported (H.264, H.265, VP9, AV1)
- **Resolution**: Check video resolution matches expected quality
- **Frame Rate**: Verify FPS is consistent and within expected range
- **Bitrate**: Validate video bitrate is appropriate for quality level
- **Keyframe Intervals**: Check for proper GOP structure

### 3. Audio Stream Validation
- **Stream Presence**: Verify audio stream exists
- **Audio Codec**: Validate codec (AAC, MP3, AC-3, E-AC-3, Opus)
- **Sample Rate**: Check audio sample rate (typically 44.1kHz or 48kHz)
- **Channels**: Verify channel count (stereo, 5.1, etc.)
- **Audio-Video Sync**: Ensure A/V synchronization

### 4. Duration Validation
- **Actual Duration**: Extract actual video duration from metadata
- **Expected Duration**: Calculate expected duration from M3U8 playlist
- **Duration Comparison**: Compare actual vs expected with tolerance (default 5%)
- **Missing Segments**: Detect if initial or final segments are missing
- **Discontinuities**: Check for unexpected gaps in timeline

### 5. Corruption Detection
- **Full Decode Test**: Attempt to decode entire video to detect corruption
- **Error Analysis**: Parse FFmpeg error output for corruption indicators
- **Frame Loss**: Detect missing or corrupted frames
- **Container Integrity**: Validate MP4 container structure

### 6. Metadata Validation
- **Format Information**: Verify container format is valid MP4
- **Codec Information**: Extract and validate codec details
- **Technical Metadata**: Verify all required metadata fields are present

## Validation Workflow

```
┌─────────────────────┐
│  Find MP4 Files     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Load Matching      │
│  M3U8 Playlists     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Run Validation     │
│  Tests (Parallel)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Collect Results    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Generate Reports   │
│  (JSON + Text)      │
└─────────────────────┘
```

## Test Execution

### Manual Validation
```bash
# Validate all downloads in default directory
python video_validator.py

# Validate specific directory
python video_validator.py path/to/downloads
```

### Automated Integration
The validator can be integrated into the download workflow:

```python
from video_validator import VideoValidator

# After download completes
validator = VideoValidator()
result = await validator.validate_video_file(
    video_path=Path("downloads/video.mp4"),
    playlist_path=Path("downloads/playlist_123.m3u8")
)

if not result['valid']:
    # Handle validation failure
    print(f"Validation failed: {result['all_issues']}")
```

## Report Format

### JSON Report Structure
```json
{
  "report_timestamp": "20241125_143022",
  "summary": {
    "total_files": 5,
    "passed": 4,
    "failed": 1,
    "pass_rate": "80.0%"
  },
  "results": [
    {
      "file_name": "video.mp4",
      "file_path": "downloads/video.mp4",
      "file_size_mb": 485.23,
      "valid": true,
      "all_issues": [],
      "all_warnings": ["Duration slightly off by 2.3s"],
      "tests": {
        "streams": {...},
        "duration": {...},
        "corruption": {...}
      },
      "video_details": {
        "codec": "h264",
        "resolution": "1920x1080",
        "fps": 25.0,
        "bitrate": 2500000
      },
      "audio_details": {
        "codec": "aac",
        "sample_rate": 48000,
        "channels": 2
      },
      "file_hash_sha256": "abc123..."
    }
  ]
}
```

### Text Report Example
```
================================================================================
VIDEO VALIDATION REPORT
================================================================================
Generated: 2024-11-25 14:30:22
Total Files: 5
Passed: 4 (80.0%)
Failed: 1 (20.0%)
================================================================================

✅ PASS: episode_01.mp4
  File Size: 485.23 MB
  Duration: 2435.60s (40.6 min)
  Video: h264 1920x1080 @ 25.00fps
  Audio: aac 2ch @ 48000Hz
  Warnings:
    - Duration slightly off: Expected 2438.00s, got 2435.60s (diff: 2.40s)
  Hash: abc123def456...

❌ FAIL: episode_02.mp4
  File Size: 125.50 MB
  Duration: 350.20s (5.8 min)
  Video: h264 1920x1080 @ 25.00fps
  Audio: aac 2ch @ 48000Hz
  Issues:
    - Duration mismatch: Expected 2440.00s, got 350.20s (diff: 2089.80s, tolerance: 122.00s)
  Hash: def789ghi012...
```

## Pass/Fail Criteria

### PASS Criteria
- ✅ File exists and is readable
- ✅ File size > 0 bytes
- ✅ Video stream present with valid codec
- ✅ Audio stream present (or acceptable for silent content)
- ✅ Duration within tolerance of expected (±5% default)
- ✅ No corruption errors detected during decode test
- ✅ Valid MP4 container structure

### FAIL Criteria
- ❌ File missing or unreadable
- ❌ File size is 0 bytes
- ❌ No video stream found
- ❌ Duration differs by more than tolerance threshold
- ❌ Corruption detected during decode test
- ❌ Invalid or unsupported codec
- ❌ Incomplete or truncated video

### WARNING Criteria (Not failures, but flagged)
- ⚠️ No audio stream (might be intentional)
- ⚠️ Unusual codec used
- ⚠️ Duration within tolerance but slightly off
- ⚠️ Very short video duration (< 1 minute)
- ⚠️ Resolution mismatch with expected quality

## Tolerance Settings

```python
# Duration tolerance (default 5%)
DURATION_TOLERANCE_PERCENT = 5.0

# Example: For 40-minute video (2400s)
# Acceptable range: 2280s - 2520s (±120s)

# Can be adjusted per validation:
validator = VideoValidator()
result = await validator.validate_duration(
    video_info=info,
    expected_duration=2400,
    tolerance_percent=3.0  # Stricter 3% tolerance
)
```

## Common Issues and Detection

### Issue: Missing First 5-6 Minutes
**Detection:**
- Duration significantly shorter than expected
- Playlist duration vs actual duration mismatch

**Report:**
```
Duration mismatch: Expected 2440.00s, got 350.20s (diff: 2089.80s)
```

### Issue: Video Corruption
**Detection:**
- FFmpeg decode errors
- Incomplete frames
- Container structure issues

**Report:**
```
Video corruption detected: [h264 @ 0x...] concealing 125 DC, 125 AC, 125 MV errors
```

### Issue: Audio-Video Desync
**Detection:**
- Timestamp analysis
- Stream duration comparison

**Report:**
```
Audio duration (2435.2s) differs from video duration (2440.1s)
```

## Integration with Hotstar Downloader

Add validation hook to `hotstar_auto_downloader.py`:

```python
async def auto_download(self, variant, headers, timestamp, playlist_url, page_title=""):
    """Automatically download using ffmpeg"""
    # ... existing code ...
    
    # Add validation after download
    await self.download_with_ffmpeg(variant['url'], headers, output_path)
    
    # Validate the downloaded file
    from video_validator import VideoValidator
    validator = VideoValidator(downloads_dir=str(self.downloads_dir))
    
    playlist_file = self.downloads_dir / f"playlist_{timestamp}.m3u8"
    result = await validator.validate_video_file(output_path, playlist_file)
    
    if not result['valid']:
        print(f"\n⚠️  VALIDATION FAILED!")
        print(f"   Issues: {', '.join(result['all_issues'])}")
        # Optionally retry download or alert user
```

## Continuous Monitoring

For production use, set up automated validation:

```bash
# Cron job to validate all downloads daily
0 2 * * * cd /path/to/Stream_collector && python video_validator.py >> validation.log 2>&1
```

## Performance Considerations

- **Corruption Check**: Most time-consuming (full decode)
- **Parallel Validation**: Process multiple files concurrently
- **Skip Re-validation**: Track validated files by hash to avoid duplicate checks

## Exit Codes

- `0`: All files passed validation
- `1`: One or more files failed validation
- `2`: No files found to validate

## Dependencies

- Python 3.8+
- FFmpeg/FFprobe installed and in PATH
- asyncio for async operations
- Standard library modules (json, pathlib, hashlib, subprocess)
