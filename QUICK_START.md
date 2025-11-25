# Quick Start Guide - Audio Merge & Testing

## What Changed?

Your Hotstar downloader now **downloads audio and video separately**, then **merges them with perfect sync**, and **validates everything automatically**!

## Quick Commands

### 1. Basic Download (Recommended for Most Users)
```powershell
python hotstar_auto_downloader.py "https://www.hotstar.com/in/shows/..."
```

**What happens:**
- ✅ Detects M3U8 playlist automatically
- ✅ Downloads video stream (no audio)
- ✅ Downloads all audio streams separately
- ✅ Merges with perfect sync
- ✅ Validates automatically
- ✅ Reports any issues

**Output you'll see:**
```
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
```

### 2. Auto-Retry Download (Best for Reliability)
```powershell
python auto_test_redownload.py "https://www.hotstar.com/..." 3
```

**What happens:**
- Downloads video
- Validates comprehensively (5 tests)
- If validation fails → re-downloads automatically
- Keeps trying until perfect (max 3 attempts)
- Archives failed attempts

**Use this when:**
- You want guaranteed perfect downloads
- Network is unstable
- You've had sync issues before

### 3. Validate Existing File
```powershell
python continuous_validator.py downloads\my_video.mp4
```

**What happens:**
- Runs 5 comprehensive tests
- Generates detailed report
- Shows exactly what's wrong (if anything)

**Use this when:**
- You want to check an old download
- Verifying download quality
- Debugging issues

### 4. Monitor Downloads Folder
```powershell
python continuous_validator.py
```

**What happens:**
- Watches `downloads/` folder
- Auto-validates any new MP4 files
- Generates reports automatically
- Alerts on failures

**Use this when:**
- Running multiple downloads
- Batch processing
- Want hands-free validation

## What Gets Tested?

Every download is tested for:

1. **Video Info** - Can the file be parsed?
2. **Audio/Video Sync** - Are they aligned? (±2 seconds tolerance)
3. **Corruption** - Full decode test to find any errors
4. **Frame Continuity** - Are all frames present?
5. **Audio Quality** - Proper codec, sample rate, channels?

## What's New vs Old Version?

| Feature | Old Version | New Version |
|---------|------------|-------------|
| Audio download | Embedded with video | Separate download |
| Sync handling | Hope for the best | FFmpeg sync flags |
| Validation | Manual check | Automatic 5-test validation |
| Failed downloads | Lost forever | Auto-retry until perfect |
| Multi-audio | Single track | All available languages |
| Reports | None | JSON + text reports |

## Troubleshooting Quick Fixes

### "Audio/Video sync mismatch"
**Fix:** Use auto-retry mode - usually fixes on 2nd attempt
```powershell
python auto_test_redownload.py "url" 3
```

### "No audio stream found"
**Fix:** Video has embedded audio, downloader will handle it automatically

### "Corruption detected"
**Fix:** Auto-retry will re-download clean version

### Multiple failures
**Fix:** Check failed files in downloads folder (renamed with `_FAILED_attempt1`)

## File Locations

- **Downloads:** `downloads/`
- **Validation Reports:** `validation_reports/`
- **Temp Files:** `downloads/temp/` (cleaned automatically)
- **Failed Downloads:** `downloads/*_FAILED_attempt*.mp4`

## Tips

1. **Use auto-retry for important downloads** - Guarantees quality
2. **Check validation reports** if something seems off
3. **Keep temp files on failure** - Helps debugging
4. **Multiple audio tracks?** - All languages are downloaded and embedded

## Example Workflow

```powershell
# 1. Download with auto-retry (recommended)
python auto_test_redownload.py "https://www.hotstar.com/in/shows/my-show" 3

# 2. If download succeeded, check the file
dir downloads\*.mp4 | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# 3. Check validation report
dir validation_reports\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# 4. Play the video to verify quality manually
```

## Need More Details?

See `AUDIO_MERGE_TESTING_GUIDE.md` for complete documentation.

## Summary

✅ **Audio and video download separately** for better quality  
✅ **Perfect sync** with FFmpeg sync flags  
✅ **Automatic validation** after every download  
✅ **Auto-retry** on failures  
✅ **Multi-audio support** for different languages  
✅ **Detailed reports** for debugging  

**No more broken downloads!**
