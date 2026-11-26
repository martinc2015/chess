@echo off
rem Chess Clone - apaga el servidor que dejo corriendo "Abrir Chess Clone.bat".
rem Solo cierra el proceso si en el puerto 5000 responde Chess Clone.

title Cerrar Chess Clone
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue; if (-not $c) { 'Chess Clone no estaba abierto.'; exit }; try { $ok = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5000/api/health' -TimeoutSec 2).Content -match 'ok' } catch { $ok = $false }; if (-not $ok) { 'El puerto 5000 lo usa otro programa: no se cerro nada.'; exit }; foreach ($id in ($c.OwningProcess | Sort-Object -Unique)) { $p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id); Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; if ($p) { $parent = Get-Process -Id $p.ParentProcessId -ErrorAction SilentlyContinue; if ($parent -and $parent.ProcessName -like 'python*') { Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue } } }; 'Chess Clone cerrado.'"
rem Deja leer el mensaje 2 segundos antes de cerrar la ventana.
ping -n 3 127.0.0.1 >nul
