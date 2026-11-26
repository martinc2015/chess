@echo off
rem Chess Clone - doble click para jugar.
rem Arranca el servidor en segundo plano (sin ventana) y abre el navegador.
rem Esta ventana se cierra sola; el juego sigue funcionando.
rem Para apagar el servidor: "Cerrar Chess Clone.bat".

title Chess Clone
cd /d "%~dp0"
set "URL=http://127.0.0.1:5000"
set "PY=%CD%\.venv\Scripts\python.exe"
set "LOG=%TEMP%\chess-clone"

rem Si ya esta corriendo, solo abre el navegador.
call :running && goto :open

rem Primera vez (o entorno roto): crea el entorno e instala dependencias.
if not exist "%PY%" (
    echo Creando entorno virtual...
    python -m venv .venv || goto :error
)
"%PY%" -c "import flask, chess" 2>nul || (
    echo Instalando dependencias...
    "%PY%" -m pip install -r requirements.txt || goto :error
)

rem Servidor oculto: no depende de esta ventana.
echo Iniciando Chess Clone...
powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -ArgumentList '-m','flask','--app','app','run','--host','127.0.0.1','--port','5000' -WorkingDirectory '%CD%' -WindowStyle Hidden -RedirectStandardOutput '%LOG%.out.log' -RedirectStandardError '%LOG%.err.log'"

rem Espera hasta 30 s a que responda.
set /a tries=0
:wait
call :running && goto :open
set /a tries+=1
if %tries% geq 30 goto :failed
ping -n 2 127.0.0.1 >nul
goto :wait

:open
start "" %URL%
exit /b 0

:running
curl.exe -sf -o nul --max-time 1 %URL%/api/health >nul 2>&1
exit /b %errorlevel%

:failed
echo.
echo Chess Clone no arranco. Detalle del error:
echo.
type "%LOG%.err.log"
pause
exit /b 1

:error
echo.
echo No se pudo preparar el entorno. Revisa que Python este instalado.
pause
exit /b 1
