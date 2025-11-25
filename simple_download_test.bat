@echo off
echo ========================================
echo Hotstar Download with Auto-Validation
echo ========================================
echo.
echo This will:
echo 1. Launch Firefox with ad blocking
echo 2. Open the Hotstar page
echo 3. Detect M3U8 playlist automatically
echo 4. Download video + audio separately
echo 5. Merge with perfect sync
echo 6. Validate comprehensively
echo.
echo Please PLAY THE VIDEO when the browser opens!
echo.
pause

python hotstar_auto_downloader.py "https://www.hotstar.com/in/shows/laughter-chefs-unlimited-entertainment/1971003517/navaratri-fiesta-with-mexican-tadka/1971043565/watch?episodeNumber=35&seasonId=1971010614" --reset-profile

echo.
echo ========================================
echo Download Complete!
echo ========================================
echo.
echo Checking downloaded files...
dir /O-D /B downloads\*.mp4 2>nul

echo.
echo Validation reports:
dir /O-D /B validation_reports\*.json 2>nul

echo.
pause
