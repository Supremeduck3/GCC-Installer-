@echo off
setlocal

cd /d "%~dp0"
echo ==============================================
echo   C Setup Assistant - Build do executavel
echo ==============================================

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON=py"
) else (
    where python >nul 2>&1
    if not %errorlevel%==0 (
        echo Python nao foi encontrado. Instale o Python 3 e marque Add Python to PATH.
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

%PYTHON% -m pip install --upgrade pyinstaller
if not %errorlevel%==0 (
    echo Falha ao instalar o PyInstaller.
    pause
    exit /b 1
)

%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name C-Setup-Assistant instalador_c_gui.py
if not %errorlevel%==0 (
    echo Falha ao compilar o executavel.
    pause
    exit /b 1
)

echo.
echo Executavel criado em:
dir /b dist\C-Setup-Assistant.exe
if exist dist\C-Setup-Assistant.exe (
    echo dist\C-Setup-Assistant.exe
) else (
    echo O executavel nao foi encontrado.
)
echo.
pause
