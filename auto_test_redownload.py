#!/usr/bin/env python3
"""
Auto Test & Re-download Script
Continuously tests downloads and re-downloads if issues are found
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
import subprocess


class AutoTester:
    def __init__(self, url, max_retries=3):
        self.url = url
        self.max_retries = max_retries
        self.downloads_dir = Path("downloads")
        self.reports_dir = Path("validation_reports")
        
    async def run_downloader(self, attempt_num):
        """Run the downloader script"""
        print(f"\n{'='*80}")
        print(f"🚀 DOWNLOAD ATTEMPT {attempt_num}/{self.max_retries}")
        print(f"{'='*80}\n")
        
        # Use python executable directly
        import os
        script_path = os.path.join(os.path.dirname(__file__), 'hotstar_auto_downloader.py')
        
        cmd = [
            sys.executable,
            script_path,
            self.url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(__file__) or '.'
        )
        
        # Stream output in real-time
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(line.decode().rstrip())
        
        await process.wait()
        
        return process.returncode == 0
    
    async def find_latest_download(self):
        """Find the most recently downloaded MP4"""
        mp4_files = list(self.downloads_dir.glob("*.mp4"))
        if not mp4_files:
            return None
        
        # Sort by modification time
        mp4_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return mp4_files[0]
    
    async def validate_download(self, video_path):
        """Validate a downloaded file"""
        print(f"\n{'='*80}")
        print(f"🔍 VALIDATING: {video_path.name}")
        print(f"{'='*80}\n")
        
        # Use python executable directly
        import os
        validator_path = os.path.join(os.path.dirname(__file__), 'continuous_validator.py')
        
        cmd = [
            sys.executable,
            validator_path,
            str(video_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(__file__) or '.'
        )
        
        # Stream output
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(line.decode().rstrip())
        
        await process.wait()
        
        # Check the validation report
        return await self.check_validation_result(video_path)
    
    async def check_validation_result(self, video_path):
        """Check if validation passed by reading the latest report"""
        # Find matching validation report
        video_stem = video_path.stem
        reports = list(self.reports_dir.glob(f"{video_stem}*_validation.json"))
        
        if not reports:
            print("⚠️  No validation report found")
            return False
        
        # Get latest report
        reports.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_report = reports[0]
        
        try:
            data = json.loads(latest_report.read_text())
            summary = data.get('summary', {})
            
            all_passed = summary.get('all_tests_passed', False)
            total_issues = summary.get('total_issues', 0)
            total_warnings = summary.get('total_warnings', 0)
            
            print(f"\n📊 VALIDATION SUMMARY:")
            print(f"   Status: {'✅ PASSED' if all_passed else '❌ FAILED'}")
            print(f"   Issues: {total_issues}")
            print(f"   Warnings: {total_warnings}")
            
            # Detailed issue breakdown
            if total_issues > 0:
                print(f"\n❌ ISSUES FOUND:")
                for test_name, test_result in data.get('tests', {}).items():
                    issues = test_result.get('issues', [])
                    if issues:
                        print(f"   {test_name.upper()}:")
                        for issue in issues:
                            print(f"     • {issue}")
            
            # Only pass if no issues (warnings are acceptable)
            return all_passed and total_issues == 0
            
        except Exception as e:
            print(f"❌ Error reading validation report: {e}")
            return False
    
    async def run_test_cycle(self):
        """Run complete test cycle with retries"""
        print(f"\n{'#'*80}")
        print(f"# AUTO TEST & RE-DOWNLOAD CYCLE")
        print(f"# URL: {self.url}")
        print(f"# Max Retries: {self.max_retries}")
        print(f"{'#'*80}\n")
        
        for attempt in range(1, self.max_retries + 1):
            # Track files before download
            files_before = set(self.downloads_dir.glob("*.mp4"))
            
            # Run downloader
            print(f"\n⏳ Starting download attempt {attempt}...")
            download_success = await self.run_downloader(attempt)
            
            if not download_success:
                print(f"❌ Download attempt {attempt} failed")
                if attempt < self.max_retries:
                    print(f"🔄 Retrying...")
                    await asyncio.sleep(5)
                    continue
                else:
                    print(f"❌ Max retries reached. Giving up.")
                    return False
            
            # Find the new file
            await asyncio.sleep(3)  # Wait for file to be fully written
            files_after = set(self.downloads_dir.glob("*.mp4"))
            new_files = files_after - files_before
            
            if not new_files:
                # Try latest file
                latest = await self.find_latest_download()
                if latest:
                    video_path = latest
                else:
                    print(f"❌ No new download found")
                    if attempt < self.max_retries:
                        print(f"🔄 Retrying...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return False
            else:
                video_path = list(new_files)[0]
            
            print(f"\n✅ Download completed: {video_path.name}")
            print(f"📊 Size: {video_path.stat().st_size / (1024*1024):.2f} MB")
            
            # Validate
            validation_passed = await self.validate_download(video_path)
            
            if validation_passed:
                print(f"\n{'='*80}")
                print(f"✅ SUCCESS! Download validated perfectly!")
                print(f"{'='*80}")
                print(f"📁 File: {video_path}")
                print(f"📊 Size: {video_path.stat().st_size / (1024*1024):.2f} MB")
                print(f"🎉 All tests passed on attempt {attempt}/{self.max_retries}")
                return True
            else:
                print(f"\n{'='*80}")
                print(f"❌ VALIDATION FAILED on attempt {attempt}")
                print(f"{'='*80}")
                
                if attempt < self.max_retries:
                    print(f"\n🔄 Re-downloading (attempt {attempt+1}/{self.max_retries})...")
                    
                    # Rename failed file
                    failed_name = video_path.stem + f"_FAILED_attempt{attempt}" + video_path.suffix
                    failed_path = video_path.parent / failed_name
                    video_path.rename(failed_path)
                    print(f"📝 Failed file renamed to: {failed_name}")
                    
                    await asyncio.sleep(5)
                else:
                    print(f"\n❌ Max retries reached. Final attempt failed.")
                    print(f"⚠️  Please check the validation reports in: {self.reports_dir}")
                    return False
        
        return False


async def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_test_redownload.py <hotstar_url> [max_retries]")
        print("\nExample:")
        print('  python auto_test_redownload.py "https://www.hotstar.com/in/shows/..." 3')
        print("\nThis script will:")
        print("  1. Download the video")
        print("  2. Run comprehensive validation tests")
        print("  3. If validation fails, re-download automatically")
        print("  4. Repeat until success or max retries reached")
        sys.exit(1)
    
    url = sys.argv[1]
    max_retries = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    tester = AutoTester(url, max_retries)
    success = await tester.run_test_cycle()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
