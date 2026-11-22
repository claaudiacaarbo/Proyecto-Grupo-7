@echo off
cd /d "%~dp0"
set "comando_planificador=py"
where py >nul 2>nul
if errorlevel 1 set "comando_planificador=python"
where %comando_planificador% >nul 2>nul
if errorlevel 1 (
    echo Instala Python 3.10 o posterior desde https://www.python.org/downloads/
    pause
    exit /b 1
)
%comando_planificador% -X utf8 "programa\iniciar.py"
set "estado_planificador=%errorlevel%"
echo(
pause
exit /b %estado_planificador%
