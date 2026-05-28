@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
set "PYTHONW_EXE=%LocalAppData%\Programs\Python\Python314\pythonw.exe"
if exist ".venv\Scripts\python.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m privacy_alarm
) else if exist "%PYTHONW_EXE%" (
  start "" "%PYTHONW_EXE%" -m privacy_alarm
) else if exist "%PYTHON_EXE%" (
  start "" "%PYTHON_EXE%" -m privacy_alarm
) else (
  start "" pythonw -m privacy_alarm
)
