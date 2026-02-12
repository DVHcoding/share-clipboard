@echo off

pyinstaller ^
  --name="ClipboardServer" ^
  --windowed ^
  --onefile ^
  server.py

pause
