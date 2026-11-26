@echo off
rem Chess Clone - doble click para jugar.
rem Levanta el servidor y abre el navegador. Cerrar esta ventana apaga el servidor.

title Chess Clone
cd /d "%~dp0"
set "URL=http://127.0.0.1:5000"
set "PY=.venv\Scripts\python.exe"

rem Si ya esta corriendo, solo abre el navegador.
curl.exe -sf -o nul --max-time 1 %URL%/api/health && (
    start "" %URL%
    exit /b
)

rem Primera vez (o entorno roto): crea el entorno e instala dependencias.
if not exist "%PY%" (
    echo Creando entorno virtual...
    python -m venv .venv || goto :error
)
"%PY%" -c "import flask, chess" 2>nul || (
    echo Instalando dependencias...
    "%PY%" -m pip install -r requirements.txt || goto :error
)

rem Abre el navegador apenas el servidor responda.
start "" /b powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; for($i=0;$i -lt 60;$i++){try{Invoke-WebRequest -UseBasicParsing '%URL%/api/health' -TimeoutSec 1 | Out-Null; Start-Process '%URL%'; break}catch{Start-Sleep -Milliseconds 500}}"

echo Chess Clone corriendo en %URL%
echo Cerra esta ventana para apagar el servidor.
echo.
"%PY%" app.py
pause
exit /b

:error
echo.
echo No se pudo preparar el entorno. Revisa que Python este instalado.
pause
