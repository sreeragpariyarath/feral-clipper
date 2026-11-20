@echo off
cd /d "%~dp0"
where git >nul 2>nul || (echo Git is not installed. Install Git for Windows first: https://git-scm.com/download/win & pause & exit /b 1)
if not exist .git git init
git add .
git commit -m "Working pipeline: chat+scan merge, KreekCraft overlay, slice download"
echo.
echo ===== Files that will be uploaded (should be code only, no .mp4 or data\) =====
git ls-files
echo.
set /p OK=Looks right? Type y to push to GitHub: 
if /i not "%OK%"=="y" (echo Cancelled. Nothing was pushed. & pause & exit /b 0)
git remote remove origin >nul 2>nul
git remote add origin https://github.com/sreeragpariyarath/feral-clipper.git
git branch -M main
git push -u origin main
pause
