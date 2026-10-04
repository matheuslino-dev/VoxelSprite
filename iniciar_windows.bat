@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title VoxelSprite Studio

if exist ".venv\Scripts\python.exe" goto check_environment
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13)" >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
        goto check_environment
    )
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13)" >nul 2>nul
    if not errorlevel 1 (
        python -m venv .venv
        goto check_environment
    )
)
echo Instale Python 3.12 ou 3.13 de 64 bits pelo site https://www.python.org/downloads/windows/
echo Marque "Add python.exe to PATH". Depois abra este arquivo novamente.
pause
exit /b 1

:check_environment
if not exist ".venv\Scripts\python.exe" (
    echo Nao foi possivel preparar o Python. Extraia o ZIP para uma pasta com permissao de escrita.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13)" >nul 2>nul
if errorlevel 1 (
    echo A pasta .venv usa um Python incompativel. Apague somente .venv e tente com Python 3.12 ou 3.13.
    pause
    exit /b 1
)
if exist ".venv\voxelsprite_instalado.txt" goto run

echo Preparando o VoxelSprite. A primeira abertura precisa de internet...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Falha ao instalar. Confira sua conexao e as mensagens acima.
    pause
    exit /b 1
)
echo 2.0.0>".venv\voxelsprite_instalado.txt"

:run
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo O aplicativo encontrou um erro. Copie a mensagem acima ou consulte erro_voxelsprite.log.
    pause
    exit /b 1
)
endlocal
