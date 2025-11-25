#!/usr/bin/env python3
"""
Video Validator for Hotstar Downloads
Validates downloaded MP4 files for correctness and generates detailed reports
"""

import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib


class VideoValidator:
    def __init__(self, downloads_dir="downloads", reports_dir="validation_reports"):
        self.downloads_dir = Path(downloads_dir)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        self.validation_results = []
    
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
        except FileNotFoundError:
            print("❌ ffprobe not found! Install ffmpeg package.")
            return None
        except Exception as e:
            print(f"❌ Error getting video info: {e}")
            return None
    
    def get_expected_duration_from_playlist(self, playlist_path: Path) -> Optional[float]:
        """Calculate expected duration from M3U8 playlist"""
        try:
            content = playlist_path.read_text(encoding='utf-8')
            total_duration = 0.0
            
            for line in content.split('\n'):
                if line.startswith('#EXTINF:'):
                    # Extract duration from #EXTINF:duration,title
                    duration_str = line.split(':')[1].split(',')[0]
                    total_duration += float(duration_str)
            
            return total_duration if total_duration > 0 else None
        except Exception as e:
            print(f"⚠️  Error reading playlist: {e}")
            return None
    
    def calculate_file_hash(self, file_path: Path, algorithm='sha256') -> str:
        """Calculate file hash for integrity verification"""
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    async def validate_video_streams(self, video_info: Dict) -> Dict[str, any]:
        """Validate video and audio streams"""
        issues = []
        warnings = []
        
        if 'streams' not in video_info:
            issues.append("No streams found in video")
            return {'valid': False, 'issues': issues, 'warnings': warnings}
        
        has_video = False
        has_audio = False
        video_stream = None
        audio_stream = None
        
        for stream in video_info['streams']:
            codec_type = stream.get('codec_type', '')
            
            if codec_type == 'video':
                has_video = True
                video_stream = stream
                
                # Check video codec
                codec = stream.get('codec_name', '')
                if codec not in ['h264', 'hevc', 'h265', 'vp9', 'av1']:
                    warnings.append(f"Unusual video codec: {codec}")
                
                # Check for errors in video stream
                if 'disposition' in stream and stream['disposition'].get('attached_pic') == 1:
                    warnings.append("Video stream marked as attached picture")
            
            elif codec_type == 'audio':
                has_audio = True
                audio_stream = stream
                
                # Check audio codec
                codec = stream.get('codec_name', '')
                if codec not in ['aac', 'mp3', 'ac3', 'eac3', 'opus']:
                    warnings.append(f"Unusual audio codec: {codec}")
        
        if not has_video:
            issues.append("No video stream found")
        
        if not has_audio:
            warnings.append("No audio stream found")
        
        return {
            'valid': len(issues) == 0,
            'has_video': has_video,
            'has_audio': has_audio,
            'video_stream': video_stream,
            'audio_stream': audio_stream,
            'issues': issues,
            'warnings': warnings
        }
    
    async def validate_duration(self, video_info: Dict, expected_duration: Optional[float], 
                               tolerance_percent: float = 5.0) -> Dict[str, any]:
        """Validate video duration against expected duration"""
        issues = []
        warnings = []
        
        if 'format' not in video_info:
            issues.append("No format information found")
            return {'valid': False, 'issues': issues, 'warnings': warnings}
        
        actual_duration = float(video_info['format'].get('duration', 0))
        
        if actual_duration <= 0:
            issues.append("Video duration is zero or negative")
            return {'valid': False, 'actual_duration': actual_duration, 'issues': issues, 'warnings': warnings}
        
        # Check against expected duration if provided
        if expected_duration:
            tolerance = expected_duration * (tolerance_percent / 100.0)
            duration_diff = abs(actual_duration - expected_duration)
            
            if duration_diff > tolerance:
                issues.append(
                    f"Duration mismatch: Expected {expected_duration:.2f}s, "
                    f"got {actual_duration:.2f}s (diff: {duration_diff:.2f}s, "
                    f"tolerance: {tolerance:.2f}s)"
                )
            elif duration_diff > (tolerance / 2):
                warnings.append(
                    f"Duration slightly off: Expected {expected_duration:.2f}s, "
                    f"got {actual_duration:.2f}s (diff: {duration_diff:.2f}s)"
                )
        
        # Check if duration seems suspiciously short (< 1 minute for full episodes)
        if actual_duration < 60:
            warnings.append(f"Video duration is very short: {actual_duration:.2f}s")
        
        return {
            'valid': len(issues) == 0,
            'actual_duration': actual_duration,
            'expected_duration': expected_duration,
            'duration_diff': abs(actual_duration - expected_duration) if expected_duration else None,
            'issues': issues,
            'warnings': warnings
        }
    
    async def check_video_corruption(self, video_path: Path) -> Dict[str, any]:
        """Check for video corruption by attempting to decode"""
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
            
            errors = stderr.decode().strip()
            
            return {
                'valid': len(errors) == 0,
                'corruption_errors': errors if errors else None,
                'issues': [f"Video corruption detected: {errors}"] if errors else [],
                'warnings': []
            }
        except Exception as e:
            return {
                'valid': False,
                'corruption_errors': str(e),
                'issues': [f"Error checking corruption: {e}"],
                'warnings': []
            }
    
    async def validate_video_file(self, video_path: Path, 
                                  playlist_path: Optional[Path] = None) -> Dict:
        """Perform comprehensive validation on a video file"""
        print(f"\n🔍 Validating: {video_path.name}")
        
        validation_result = {
            'file_name': video_path.name,
            'file_path': str(video_path),
            'file_size_mb': video_path.stat().st_size / (1024 * 1024),
            'timestamp': datetime.now().isoformat(),
            'valid': True,
            'all_issues': [],
            'all_warnings': [],
            'tests': {}
        }
        
        # Test 1: File exists and is readable
        if not video_path.exists():
            validation_result['valid'] = False
            validation_result['all_issues'].append("File does not exist")
            return validation_result
        
        if video_path.stat().st_size == 0:
            validation_result['valid'] = False
            validation_result['all_issues'].append("File is empty (0 bytes)")
            return validation_result
        
        print("  ✓ File exists and is readable")
        
        # Test 2: Get video information
        video_info = await self.get_video_info(video_path)
        if not video_info:
            validation_result['valid'] = False
            validation_result['all_issues'].append("Could not read video metadata")
            return validation_result
        
        print("  ✓ Video metadata readable")
        
        # Test 3: Validate streams
        stream_validation = await self.validate_video_streams(video_info)
        validation_result['tests']['streams'] = stream_validation
        validation_result['all_issues'].extend(stream_validation['issues'])
        validation_result['all_warnings'].extend(stream_validation['warnings'])
        
        if stream_validation['valid']:
            print(f"  ✓ Streams valid (Video: {stream_validation['has_video']}, Audio: {stream_validation['has_audio']})")
        else:
            print(f"  ✗ Stream validation failed")
            validation_result['valid'] = False
        
        # Test 4: Validate duration
        expected_duration = None
        if playlist_path and playlist_path.exists():
            expected_duration = self.get_expected_duration_from_playlist(playlist_path)
        
        duration_validation = await self.validate_duration(video_info, expected_duration)
        validation_result['tests']['duration'] = duration_validation
        validation_result['all_issues'].extend(duration_validation['issues'])
        validation_result['all_warnings'].extend(duration_validation['warnings'])
        
        if duration_validation['valid']:
            duration = duration_validation['actual_duration']
            print(f"  ✓ Duration: {duration:.2f}s ({duration/60:.1f} min)")
        else:
            print(f"  ✗ Duration validation failed")
            validation_result['valid'] = False
        
        # Test 5: Check for corruption
        print("  ⏳ Checking for corruption (this may take a moment)...")
        corruption_check = await self.check_video_corruption(video_path)
        validation_result['tests']['corruption'] = corruption_check
        validation_result['all_issues'].extend(corruption_check['issues'])
        validation_result['all_warnings'].extend(corruption_check['warnings'])
        
        if corruption_check['valid']:
            print("  ✓ No corruption detected")
        else:
            print(f"  ✗ Corruption detected")
            validation_result['valid'] = False
        
        # Test 6: Calculate file hash for integrity
        print("  ⏳ Calculating file hash...")
        file_hash = self.calculate_file_hash(video_path)
        validation_result['file_hash_sha256'] = file_hash
        print(f"  ✓ Hash: {file_hash[:16]}...")
        
        # Test 7: Check video codec details
        if stream_validation.get('video_stream'):
            vs = stream_validation['video_stream']
            validation_result['video_details'] = {
                'codec': vs.get('codec_name'),
                'resolution': f"{vs.get('width', 0)}x{vs.get('height', 0)}",
                'fps': eval(vs.get('r_frame_rate', '0/1').replace('/', '.0/')),
                'bitrate': int(vs.get('bit_rate', 0)),
                'profile': vs.get('profile')
            }
        
        if stream_validation.get('audio_stream'):
            aus = stream_validation['audio_stream']
            validation_result['audio_details'] = {
                'codec': aus.get('codec_name'),
                'sample_rate': int(aus.get('sample_rate', 0)),
                'channels': aus.get('channels'),
                'bitrate': int(aus.get('bit_rate', 0))
            }
        
        # Final verdict
        if validation_result['valid']:
            print(f"\n✅ PASSED: {video_path.name}")
        else:
            print(f"\n❌ FAILED: {video_path.name}")
            print(f"   Issues: {', '.join(validation_result['all_issues'])}")
        
        if validation_result['all_warnings']:
            print(f"   Warnings: {', '.join(validation_result['all_warnings'])}")
        
        return validation_result
    
    async def validate_all_downloads(self) -> List[Dict]:
        """Validate all MP4 files in downloads directory"""
        mp4_files = list(self.downloads_dir.glob("*.mp4"))
        
        if not mp4_files:
            print("⚠️  No MP4 files found in downloads directory")
            return []
        
        print(f"🔍 Found {len(mp4_files)} MP4 file(s) to validate\n")
        
        results = []
        for mp4_file in mp4_files:
            # Find matching playlist file (same timestamp)
            # Extract timestamp from filename if possible
            playlist_file = None
            for m3u8 in self.downloads_dir.glob("playlist_*.m3u8"):
                # Try to match by timestamp in filename
                if mp4_file.stem.split('_')[-1] in m3u8.stem:
                    playlist_file = m3u8
                    break
            
            result = await self.validate_video_file(mp4_file, playlist_file)
            results.append(result)
            self.validation_results.append(result)
        
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """Generate detailed validation report"""
        report_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.reports_dir / f"validation_report_{report_timestamp}.json"
        
        total = len(results)
        passed = sum(1 for r in results if r['valid'])
        failed = total - passed
        
        report = {
            'report_timestamp': report_timestamp,
            'summary': {
                'total_files': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': f"{(passed/total*100):.1f}%" if total > 0 else "0%"
            },
            'results': results
        }
        
        # Save JSON report
        report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
        
        # Generate human-readable text report
        text_report = self.reports_dir / f"validation_report_{report_timestamp}.txt"
        
        report_lines = [
            "=" * 80,
            "VIDEO VALIDATION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Files: {total}",
            f"Passed: {passed} ({(passed/total*100):.1f}%)" if total > 0 else "Passed: 0 (0%)",
            f"Failed: {failed} ({(failed/total*100):.1f}%)" if total > 0 else "Failed: 0 (0%)",
            "=" * 80,
            ""
        ]
        
        for result in results:
            status = "✅ PASS" if result['valid'] else "❌ FAIL"
            report_lines.extend([
                f"\n{status}: {result['file_name']}",
                f"  File Size: {result['file_size_mb']:.2f} MB",
            ])
            
            if 'duration' in result['tests']:
                dur = result['tests']['duration'].get('actual_duration', 0)
                report_lines.append(f"  Duration: {dur:.2f}s ({dur/60:.1f} min)")
            
            if result.get('video_details'):
                vd = result['video_details']
                report_lines.append(f"  Video: {vd['codec']} {vd['resolution']} @ {vd['fps']:.2f}fps")
            
            if result.get('audio_details'):
                ad = result['audio_details']
                report_lines.append(f"  Audio: {ad['codec']} {ad['channels']}ch @ {ad['sample_rate']}Hz")
            
            if result['all_issues']:
                report_lines.append("  Issues:")
                for issue in result['all_issues']:
                    report_lines.append(f"    - {issue}")
            
            if result['all_warnings']:
                report_lines.append("  Warnings:")
                for warning in result['all_warnings']:
                    report_lines.append(f"    - {warning}")
            
            report_lines.append(f"  Hash: {result.get('file_hash_sha256', 'N/A')[:16]}...")
        
        report_lines.extend([
            "",
            "=" * 80,
            f"Detailed JSON report: {report_file.name}",
            "=" * 80
        ])
        
        text_report.write_text('\n'.join(report_lines), encoding='utf-8')
        
        print(f"\n📊 Reports generated:")
        print(f"  JSON: {report_file}")
        print(f"  Text: {text_report}")
        
        return str(report_file)


async def main():
    import sys
    
    if len(sys.argv) > 1:
        downloads_dir = sys.argv[1]
    else:
        downloads_dir = "downloads"
    
    print("🎬 Video Validation Tool")
    print("=" * 60)
    
    validator = VideoValidator(downloads_dir=downloads_dir)
    results = await validator.validate_all_downloads()
    
    if results:
        validator.generate_report(results)
        
        # Print summary
        total = len(results)
        passed = sum(1 for r in results if r['valid'])
        failed = total - passed
        
        print(f"\n{'=' * 60}")
        print(f"VALIDATION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        
        if failed > 0:
            print(f"\n⚠️  {failed} file(s) failed validation!")
            sys.exit(1)
        else:
            print(f"\n✅ All files passed validation!")
            sys.exit(0)
    else:
        print("\n⚠️  No files to validate")
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())
