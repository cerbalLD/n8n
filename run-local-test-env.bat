@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND_PORT=8000"
set "SKIP_INSTALL=0"
set "SKIP_BUILD=0"
set "CHECK_ONLY=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--help" goto help
if /I "%~1"=="/?" goto help
if /I "%~1"=="--no-install" set "SKIP_INSTALL=1"
if /I "%~1"=="--no-build" set "SKIP_BUILD=1"
if /I "%~1"=="--check" set "CHECK_ONLY=1"
shift
goto parse_args

:args_done

cd /d "%ROOT%" || exit /b 1

call :resolve_pnpm
if errorlevel 1 exit /b 1

call :resolve_python
if errorlevel 1 exit /b 1

echo Checking backend Python dependencies...
%PYTHON_CMD% -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
	echo Backend dependencies are missing for %PYTHON_CMD%.
	echo Run this first:
	echo   %PYTHON_CMD% -m pip install -r "%ROOT%\backend\requirements.txt"
	exit /b 1
)

if "%CHECK_ONLY%"=="1" (
	echo Checks passed.
	echo pnpm command: %PNPM_CMD%
	echo Python command: %PYTHON_CMD%
	if exist "%ROOT%\node_modules\.bin\turbo.cmd" (
		echo JS dependencies: installed
	) else (
		echo JS dependencies: missing, run without --check to install them.
	)
	exit /b 0
)

if "%SKIP_BUILD%"=="0" (
	call :ensure_node_deps
	if errorlevel 1 exit /b 1

	echo Building n8n. Full log: "%ROOT%\build.log"
	call %PNPM_CMD% build > "%ROOT%\build.log" 2>&1
	if errorlevel 1 (
		echo Build failed. Last 60 log lines:
		powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%ROOT%\build.log' -Tail 60"
		exit /b 1
	)
) else (
	echo Skipping n8n build.
)

echo Starting local content backend on http://127.0.0.1:%BACKEND_PORT%
start "n8n local content backend" /D "%ROOT%\backend" cmd /k %PYTHON_CMD% -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%

echo Starting n8n on http://localhost:5678
set "N8N_LOCAL_LICENSE_BYPASS=true"
set "N8N_SECURE_COOKIE=false"
set "N8N_TEMPLATES_ENABLED=true"
set "N8N_TEMPLATES_HOST=http://127.0.0.1:%BACKEND_PORT%/api/"
set "N8N_LICENSE_SERVER_URL=http://127.0.0.1:%BACKEND_PORT%/v1"
set "N8N_VERSION_NOTIFICATIONS_ENDPOINT=http://127.0.0.1:%BACKEND_PORT%/api/versions/"
set "N8N_VERSION_NOTIFICATIONS_WHATS_NEW_ENDPOINT=http://127.0.0.1:%BACKEND_PORT%/api/whats-new"
set "N8N_DYNAMIC_BANNERS_ENDPOINT=http://127.0.0.1:%BACKEND_PORT%/api/banners"
start "n8n app" /D "%ROOT%" cmd /k %PNPM_CMD% start

echo.
echo Started. Close the two opened command windows to stop the servers.
echo Backend: http://127.0.0.1:%BACKEND_PORT%
echo n8n:     http://localhost:5678
exit /b 0

:ensure_node_deps
if exist "%ROOT%\node_modules\.bin\turbo.cmd" (
	exit /b 0
)

if "%SKIP_INSTALL%"=="1" (
	echo JS dependencies are missing: "%ROOT%\node_modules\.bin\turbo.cmd"
	echo Remove --no-install or run this manually first:
	echo   %PNPM_CMD% install
	exit /b 1
)

echo JS dependencies are missing. Installing. Full log: "%ROOT%\install.log"
call %PNPM_CMD% install > "%ROOT%\install.log" 2>&1
if errorlevel 1 (
	echo Install failed. Last 80 log lines:
	powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%ROOT%\install.log' -Tail 80"
	exit /b 1
)

if not exist "%ROOT%\node_modules\.bin\turbo.cmd" (
	echo Install finished, but turbo was not found at "%ROOT%\node_modules\.bin\turbo.cmd".
	echo Check "%ROOT%\install.log" for details.
	exit /b 1
)

exit /b 0

:resolve_pnpm
where pnpm.cmd >nul 2>nul
if not errorlevel 1 (
	set "PNPM_CMD=pnpm"
	exit /b 0
)

where pnpm >nul 2>nul
if not errorlevel 1 (
	set "PNPM_CMD=pnpm"
	exit /b 0
)

where corepack.cmd >nul 2>nul
if not errorlevel 1 (
	set "PNPM_CMD=corepack pnpm"
	exit /b 0
)

where corepack >nul 2>nul
if not errorlevel 1 (
	set "PNPM_CMD=corepack pnpm"
	exit /b 0
)

echo pnpm not found, and corepack is not available.
echo Install pnpm or enable Corepack first.
exit /b 1

:resolve_python
if exist "%ROOT%\venv\Scripts\python.exe" (
	set "PYTHON_CMD="%ROOT%\venv\Scripts\python.exe""
	exit /b 0
)

if exist "%ROOT%\backend\.venv\Scripts\python.exe" (
	set "PYTHON_CMD="%ROOT%\backend\.venv\Scripts\python.exe""
	exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
	set "PYTHON_CMD=py -3"
	exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
	set "PYTHON_CMD=python"
	exit /b 0
)

echo Python not found. Install Python or create venv at "%ROOT%\venv".
exit /b 1

:help
echo Usage:
echo   run-local-test-env.bat
echo   run-local-test-env.bat --no-install
echo   run-local-test-env.bat --no-build
echo   run-local-test-env.bat --check
echo.
echo Default mode builds n8n, then starts:
echo   - backend FastAPI server on http://127.0.0.1:8000
echo   - n8n on http://localhost:5678
echo.
echo --no-install fails if node_modules are missing instead of running pnpm install.
echo --check verifies pnpm/Corepack and backend Python dependencies only.
exit /b 0
