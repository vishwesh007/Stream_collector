#!/usr/bin/env python3
"""
Run automated tests on Hotstar downloads
Quick validation script for testing workflow
"""

import asyncio
import sys
from pathlib import Path

# Import the validator
from video_validator import VideoValidator


async def run_quick_test():
    """Run quick validation test on latest download"""
    print("🧪 Running Quick Validation Test\n")
    
    validator = VideoValidator(downloads_dir='downloads')
    
    # Find the most recent MP4 file
    mp4_files = sorted(
        Path('downloads').glob('*.mp4'),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not mp4_files:
        print("❌ No MP4 files found in downloads/")
        return False
    
    latest_file = mp4_files[0]
    print(f"📁 Testing latest file: {latest_file.name}\n")
    
    # Find matching playlist
    timestamp_parts = latest_file.stem.split('_')
    playlist_file = None
    
    for m3u8 in Path('downloads').glob('playlist_*.m3u8'):
        if any(part in m3u8.stem for part in timestamp_parts[-2:]):
            playlist_file = m3u8
            break
    
    if playlist_file:
        print(f"📋 Found playlist: {playlist_file.name}\n")
    else:
        print("⚠️  No matching playlist found, skipping duration check\n")
    
    # Run validation
    result = await validator.validate_video_file(latest_file, playlist_file)
    
    # Generate mini report
    print("\n" + "=" * 60)
    print("QUICK TEST RESULTS")
    print("=" * 60)
    
    if result['valid']:
        print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION FAILED")
    
    print(f"\nFile: {result['file_name']}")
    print(f"Size: {result['file_size_mb']:.2f} MB")
    
    if 'duration' in result['tests']:
        dur = result['tests']['duration'].get('actual_duration', 0)
        print(f"Duration: {dur:.2f}s ({dur/60:.1f} minutes)")
    
    if result.get('video_details'):
        vd = result['video_details']
        print(f"Video: {vd['codec']} {vd['resolution']} @ {vd['fps']:.2f}fps")
    
    if result.get('audio_details'):
        ad = result['audio_details']
        print(f"Audio: {ad['codec']} {ad['channels']}ch @ {ad['sample_rate']}Hz")
    
    if result['all_issues']:
        print(f"\n❌ Issues Found ({len(result['all_issues'])}):")
        for issue in result['all_issues']:
            print(f"  • {issue}")
    
    if result['all_warnings']:
        print(f"\n⚠️  Warnings ({len(result['all_warnings'])}):")
        for warning in result['all_warnings']:
            print(f"  • {warning}")
    
    print("\n" + "=" * 60)
    
    return result['valid']


async def run_full_test():
    """Run full validation on all downloads"""
    print("🧪 Running Full Validation Test\n")
    
    validator = VideoValidator(downloads_dir='downloads')
    results = await validator.validate_all_downloads()
    
    if results:
        report_path = validator.generate_report(results)
        
        passed = sum(1 for r in results if r['valid'])
        failed = len(results) - passed
        
        print(f"\n{'=' * 60}")
        print(f"FULL TEST RESULTS")
        print(f"{'=' * 60}")
        print(f"Total Files: {len(results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Pass Rate: {(passed/len(results)*100):.1f}%")
        print(f"\n📊 Full report: {report_path}")
        print(f"{'=' * 60}")
        
        return failed == 0
    else:
        print("⚠️  No files to test")
        return True


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        success = await run_full_test()
    else:
        success = await run_quick_test()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
