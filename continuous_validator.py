#!/usr/bin/env python3
"""
Continuous Video Validator
Monitors downloads and runs comprehensive validation tests
"""

import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import time


class ContinuousValidator:
    def __init__(self, downloads_dir="downloads", reports_dir="validation_reports"):
        self.downloads_dir = Path(downloads_dir)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        self.validated_files = set()
        
    async def get_video_info(self, video_path: Path) -> Optional[Dict]:
        """Get detailed video information using ffprobe"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-show_error',
            str(video_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return None
        except Exception as e:
            print(f"❌ Error getting video info: {e}")
            return None
    
    async def check_audio_video_sync(self, video_path: Path) -> Dict:
        """Check if audio and video are properly synchronized"""
        info = await self.get_video_info(video_path)
        
        if not info:
            return {'valid': False, 'issues': ['Failed to get video info']}
        
        issues = []
        warnings = []
        
        video_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
        audio_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
        
        if not video_streams:
            issues.append("No video stream found")
        
        if not audio_streams:
            issues.append("No audio stream found")
        
        # Check duration sync
        if video_streams and audio_streams:
            video_duration = float(video_streams[0].get('duration', 0))
            audio_duration = float(audio_streams[0].get('duration', 0))
            
            duration_diff = abs(video_duration - audio_duration)
            
            if duration_diff > 2.0:  # 2 second tolerance
                issues.append(f"Audio/Video sync mismatch: {duration_diff:.2f}s difference")
            elif duration_diff > 0.5:
                warnings.append(f"Minor sync difference: {duration_diff:.2f}s")
        
        # Check for audio codec issues
        for audio in audio_streams:
            codec = audio.get('codec_name', '')
            if codec not in ['aac', 'mp3', 'opus', 'vorbis']:
                warnings.append(f"Unusual audio codec: {codec}")
        
        # Check for multiple audio tracks
        if len(audio_streams) > 1:
            print(f"✅ Multiple audio tracks found: {len(audio_streams)}")
            for idx, audio in enumerate(audio_streams):
                lang = audio.get('tags', {}).get('language', 'unknown')
                codec = audio.get('codec_name', 'unknown')
                print(f"   Track {idx+1}: {lang} ({codec})")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'video_streams': len(video_streams),
            'audio_streams': len(audio_streams),
            'video_duration': video_streams[0].get('duration', 0) if video_streams else 0,
            'audio_duration': audio_streams[0].get('duration', 0) if audio_streams else 0
        }
    
    async def check_video_corruption(self, video_path: Path) -> Dict:
        """Check for video corruption by attempting full decode"""
        cmd = [
            'ffmpeg',
            '-v', 'error',
            '-i', str(video_path),
            '-f', 'null',
            '-'
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            error_output = stderr.decode()
            
            if process.returncode == 0 and not error_output:
                return {'valid': True, 'issues': [], 'warnings': []}
            else:
                issues = []
                if error_output:
                    # Parse errors
                    error_lines = [line for line in error_output.split('\n') if line.strip()]
                    if error_lines:
                        issues.append(f"Corruption detected: {len(error_lines)} error(s)")
                        for line in error_lines[:5]:  # First 5 errors
                            issues.append(f"  {line}")
                
                return {'valid': False, 'issues': issues, 'warnings': []}
                
        except Exception as e:
            return {'valid': False, 'issues': [f'Corruption check failed: {e}'], 'warnings': []}
    
    async def check_frame_continuity(self, video_path: Path) -> Dict:
        """Check for missing frames or discontinuities"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-count_packets',
            '-show_entries', 'stream=nb_read_packets,nb_frames,duration,avg_frame_rate',
            '-of', 'json',
            str(video_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                stream = data.get('streams', [{}])[0]
                
                nb_frames = int(stream.get('nb_frames', 0))
                nb_packets = int(stream.get('nb_read_packets', 0))
                duration = float(stream.get('duration', 0))
                
                issues = []
                warnings = []
                
                # Check if frame count seems reasonable
                if nb_frames == 0:
                    issues.append("No frames detected")
                
                # Check packet/frame consistency
                if nb_frames > 0 and nb_packets > 0:
                    packet_frame_ratio = nb_packets / nb_frames
                    if packet_frame_ratio > 1.5:
                        warnings.append(f"High packet/frame ratio: {packet_frame_ratio:.2f}")
                
                # Check expected frames based on duration
                avg_fps = stream.get('avg_frame_rate', '0/0')
                if '/' in avg_fps:
                    num, den = map(int, avg_fps.split('/'))
                    if den > 0:
                        fps = num / den
                        expected_frames = int(duration * fps)
                        if expected_frames > 0:
                            frame_diff_pct = abs(nb_frames - expected_frames) / expected_frames * 100
                            if frame_diff_pct > 5:
                                warnings.append(f"Frame count mismatch: expected ~{expected_frames}, got {nb_frames} ({frame_diff_pct:.1f}% diff)")
                
                return {
                    'valid': len(issues) == 0,
                    'issues': issues,
                    'warnings': warnings,
                    'nb_frames': nb_frames,
                    'nb_packets': nb_packets,
                    'duration': duration
                }
            else:
                return {'valid': False, 'issues': ['Frame continuity check failed'], 'warnings': []}
                
        except Exception as e:
            return {'valid': False, 'issues': [f'Frame check error: {e}'], 'warnings': []}
    
    async def check_audio_continuity(self, video_path: Path) -> Dict:
        """Check for audio gaps or discontinuities"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name,sample_rate,channels,duration',
            '-show_entries', 'format=duration',
            '-of', 'json',
            str(video_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                
                issues = []
                warnings = []
                
                streams = data.get('streams', [])
                if not streams:
                    issues.append("No audio stream for continuity check")
                    return {'valid': False, 'issues': issues, 'warnings': warnings}
                
                audio = streams[0]
                audio_duration = float(audio.get('duration', 0))
                format_duration = float(data.get('format', {}).get('duration', 0))
                
                # Check if audio duration matches container duration
                if audio_duration > 0 and format_duration > 0:
                    duration_diff = abs(audio_duration - format_duration)
                    if duration_diff > 1.0:
                        warnings.append(f"Audio duration mismatch with container: {duration_diff:.2f}s")
                
                # Check sample rate
                sample_rate = int(audio.get('sample_rate', 0))
                if sample_rate < 44100:
                    warnings.append(f"Low sample rate: {sample_rate} Hz")
                
                # Check channels
                channels = int(audio.get('channels', 0))
                if channels < 1:
                    issues.append("No audio channels detected")
                
                return {
                    'valid': len(issues) == 0,
                    'issues': issues,
                    'warnings': warnings,
                    'audio_duration': audio_duration,
                    'sample_rate': sample_rate,
                    'channels': channels
                }
            else:
                return {'valid': False, 'issues': ['Audio continuity check failed'], 'warnings': []}
                
        except Exception as e:
            return {'valid': False, 'issues': [f'Audio check error: {e}'], 'warnings': []}
    
    async def comprehensive_validation(self, video_path: Path) -> Dict:
        """Run all validation checks"""
        print(f"\n{'='*80}")
        print(f"🔍 COMPREHENSIVE VALIDATION: {video_path.name}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        results = {
            'file': str(video_path),
            'timestamp': datetime.now().isoformat(),
            'file_size_mb': video_path.stat().st_size / (1024*1024),
            'tests': {}
        }
        
        # Test 1: Basic info
        print("\n📊 Test 1/5: Getting video information...")
        info = await self.get_video_info(video_path)
        if info:
            print("✅ Video info retrieved")
            results['video_info'] = {
                'format': info.get('format', {}).get('format_name', 'unknown'),
                'duration': float(info.get('format', {}).get('duration', 0)),
                'bit_rate': int(info.get('format', {}).get('bit_rate', 0)),
                'video_codec': next((s.get('codec_name') for s in info.get('streams', []) if s.get('codec_type') == 'video'), 'none'),
                'audio_codec': next((s.get('codec_name') for s in info.get('streams', []) if s.get('codec_type') == 'audio'), 'none')
            }
        else:
            print("❌ Failed to get video info")
            results['tests']['info'] = {'valid': False, 'issues': ['Failed to retrieve info']}
        
        # Test 2: Audio/Video sync
        print("\n🎬 Test 2/5: Checking audio/video sync...")
        sync_result = await self.check_audio_video_sync(video_path)
        results['tests']['sync'] = sync_result
        if sync_result['valid']:
            print(f"✅ Sync check passed - {sync_result['audio_streams']} audio track(s)")
        else:
            print(f"❌ Sync issues detected:")
            for issue in sync_result['issues']:
                print(f"   • {issue}")
        
        # Test 3: Corruption check
        print("\n🔍 Test 3/5: Checking for video corruption...")
        corruption_result = await self.check_video_corruption(video_path)
        results['tests']['corruption'] = corruption_result
        if corruption_result['valid']:
            print("✅ No corruption detected")
        else:
            print(f"❌ Corruption detected:")
            for issue in corruption_result['issues']:
                print(f"   • {issue}")
        
        # Test 4: Frame continuity
        print("\n🎞️  Test 4/5: Checking frame continuity...")
        frame_result = await self.check_frame_continuity(video_path)
        results['tests']['frames'] = frame_result
        if frame_result['valid']:
            print(f"✅ Frame continuity OK - {frame_result.get('nb_frames', 0)} frames")
        else:
            print(f"❌ Frame issues:")
            for issue in frame_result['issues']:
                print(f"   • {issue}")
        
        # Test 5: Audio continuity
        print("\n🎵 Test 5/5: Checking audio continuity...")
        audio_result = await self.check_audio_continuity(video_path)
        results['tests']['audio'] = audio_result
        if audio_result['valid']:
            print(f"✅ Audio continuity OK - {audio_result.get('channels', 0)} channel(s)")
        else:
            print(f"❌ Audio issues:")
            for issue in audio_result['issues']:
                print(f"   • {issue}")
        
        # Summary
        elapsed = time.time() - start_time
        
        all_valid = all(
            results['tests'][test].get('valid', False) 
            for test in results['tests']
        )
        
        total_issues = sum(
            len(results['tests'][test].get('issues', [])) 
            for test in results['tests']
        )
        
        total_warnings = sum(
            len(results['tests'][test].get('warnings', [])) 
            for test in results['tests']
        )
        
        results['summary'] = {
            'all_tests_passed': all_valid,
            'total_issues': total_issues,
            'total_warnings': total_warnings,
            'validation_time_seconds': elapsed
        }
        
        print(f"\n{'='*80}")
        if all_valid and total_warnings == 0:
            print("✅ ALL TESTS PASSED - Video is PERFECT!")
        elif all_valid:
            print(f"✅ All tests passed with {total_warnings} warning(s)")
        else:
            print(f"❌ VALIDATION FAILED - {total_issues} issue(s) found")
        print(f"⏱️  Validation completed in {elapsed:.2f}s")
        print(f"{'='*80}\n")
        
        return results
    
    async def save_report(self, results: Dict):
        """Save validation report to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        video_name = Path(results['file']).stem
        
        # JSON report
        json_file = self.reports_dir / f"{video_name}_{timestamp}_validation.json"
        json_file.write_text(json.dumps(results, indent=2), encoding='utf-8')
        
        # Text report
        text_file = self.reports_dir / f"{video_name}_{timestamp}_validation.txt"
        
        report_lines = [
            "="*80,
            f"VALIDATION REPORT: {video_name}",
            "="*80,
            f"File: {results['file']}",
            f"Size: {results['file_size_mb']:.2f} MB",
            f"Timestamp: {results['timestamp']}",
            "",
            "VIDEO INFO:",
            f"  Format: {results.get('video_info', {}).get('format', 'unknown')}",
            f"  Duration: {results.get('video_info', {}).get('duration', 0):.2f}s",
            f"  Video Codec: {results.get('video_info', {}).get('video_codec', 'none')}",
            f"  Audio Codec: {results.get('video_info', {}).get('audio_codec', 'none')}",
            "",
            "TEST RESULTS:",
        ]
        
        for test_name, test_result in results['tests'].items():
            status = "✅ PASS" if test_result.get('valid', False) else "❌ FAIL"
            report_lines.append(f"\n{test_name.upper()}: {status}")
            
            if test_result.get('issues'):
                report_lines.append("  Issues:")
                for issue in test_result['issues']:
                    report_lines.append(f"    • {issue}")
            
            if test_result.get('warnings'):
                report_lines.append("  Warnings:")
                for warning in test_result['warnings']:
                    report_lines.append(f"    ⚠ {warning}")
        
        summary = results['summary']
        report_lines.extend([
            "",
            "="*80,
            "SUMMARY:",
            f"  Overall Status: {'✅ PASSED' if summary['all_tests_passed'] else '❌ FAILED'}",
            f"  Total Issues: {summary['total_issues']}",
            f"  Total Warnings: {summary['total_warnings']}",
            f"  Validation Time: {summary['validation_time_seconds']:.2f}s",
            "="*80
        ])
        
        text_file.write_text('\n'.join(report_lines), encoding='utf-8')
        
        print(f"📄 Reports saved:")
        print(f"   JSON: {json_file}")
        print(f"   Text: {text_file}")
    
    async def monitor_downloads(self, interval=5):
        """Continuously monitor downloads directory for new files"""
        print("👁️  Starting continuous validation monitor...")
        print(f"📁 Watching: {self.downloads_dir}")
        print(f"🔄 Checking every {interval} seconds")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Find MP4 files
                mp4_files = list(self.downloads_dir.glob("*.mp4"))
                
                # Find new files
                new_files = [f for f in mp4_files if f not in self.validated_files]
                
                for video_file in new_files:
                    # Wait a bit to ensure download is complete
                    await asyncio.sleep(2)
                    
                    # Check if file size is stable (download complete)
                    size1 = video_file.stat().st_size
                    await asyncio.sleep(2)
                    size2 = video_file.stat().st_size
                    
                    if size1 == size2 and size2 > 0:
                        print(f"\n🆕 New download detected: {video_file.name}")
                        
                        # Validate
                        results = await self.comprehensive_validation(video_file)
                        
                        # Save report
                        await self.save_report(results)
                        
                        # Mark as validated
                        self.validated_files.add(video_file)
                        
                        # If validation failed, alert
                        if not results['summary']['all_tests_passed']:
                            print(f"\n⚠️  WARNING: Validation failed for {video_file.name}")
                            print(f"   Please review the report in {self.reports_dir}")
                
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping monitor...")


async def main():
    import sys
    
    validator = ContinuousValidator(downloads_dir='downloads')
    
    if len(sys.argv) > 1:
        # Validate specific file
        video_path = Path(sys.argv[1])
        if not video_path.exists():
            print(f"❌ File not found: {video_path}")
            sys.exit(1)
        
        results = await validator.comprehensive_validation(video_path)
        await validator.save_report(results)
        
        sys.exit(0 if results['summary']['all_tests_passed'] else 1)
    else:
        # Continuous monitoring mode
        await validator.monitor_downloads()


if __name__ == '__main__':
    asyncio.run(main())
