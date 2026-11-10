@echo off
REM 打包 TouchpadRescue 为单文件 exe
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name TouchpadRescue ^
  --distpath ..\dist --workpath ..\build --specpath ..\build ^
  --icon ..\assets\app.ico ^
  --exclude-module numpy --exclude-module scipy --exclude-module matplotlib ^
  --exclude-module pandas --exclude-module PyQt5 --exclude-module PySide2 ^
  tp_app.py
echo.
echo 打包完成: ..\dist\TouchpadRescue.exe
pause
