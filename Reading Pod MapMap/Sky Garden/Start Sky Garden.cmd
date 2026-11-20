@echo off
setlocal
pushd "%~dp0..\.."
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" "%~dp0play_cue.py" --video --read %*
set "result=%ERRORLEVEL%"
popd

if not "%result%"=="0" if not "%result%"=="130" pause
exit /b %result%
