@echo off
cd /d "%~dp0"
echo.
echo === Step 1: check the new layout works (nothing is deleted yet) ===
python -c "import clipper.common, clipper.pipeline, clipper.sources.vod_source, clipper.detect.frame_scan, clipper.render.media; print('imports OK')"
if errorlevel 1 (echo.& echo The new layout failed to import. Nothing was changed. Send me this window.& pause & exit /b 1)
python vod.py --help >nul 2>nul
if errorlevel 1 (echo vod.py --help failed. Nothing was changed. Send me this window.& pause & exit /b 1)
python scan.py --help >nul 2>nul
if errorlevel 1 (echo scan.py --help failed. Nothing was changed. Send me this window.& pause & exit /b 1)
python merge.py --help >nul 2>nul
if errorlevel 1 (echo merge.py --help failed. Nothing was changed. Send me this window.& pause & exit /b 1)
echo vod.py / scan.py / merge.py start OK

echo.
echo === Step 2: remove the old copies that now live in clipper\ and tools\ ===
for %%F in (common chat_twitch audio_detect detector discovery judge transcribe local_models media overlay facecam_auto pipeline frame apitest rerender_ready update_knowledge setup_models transcript) do (
  if exist %%F.py git rm -q -f %%F.py
)

echo.
echo === Step 3: move backup files into backups\ ===
if not exist backups mkdir backups
move /y *.bak*.py backups\ >nul 2>nul
move /y config.bak*.json backups\ >nul 2>nul
move /y config.backup.json backups\ >nul 2>nul
move /y gta6_knowledge.*.bak.json backups\ >nul 2>nul

echo.
echo === Step 4: save a snapshot ===
git add -A
git commit -m "Restructure into clipper/ package and tools/; split vod.py and scan.py; shared helpers in common"
echo.
git status --short
echo.
echo Done. To upload: git push
pause
