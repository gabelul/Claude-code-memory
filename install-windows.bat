@echo off
REM Claude Code Memory Solution - Windows Installer
REM Automatically clones from GitHub and sets up both Python indexer and Node.js MCP server

setlocal enabledelayedexpansion

REM Configuration
set REPO_URL=https://github.com/gabelul/Claude-code-memory.git
set INSTALL_DIR=%USERPROFILE%\Claude-code-memory
set MCP_SERVER_DIR=%INSTALL_DIR%\mcp-qdrant-memory

echo Claude Code Memory Solution - Windows Installer
echo =================================================

REM Check prerequisites
echo Checking prerequisites...

REM Check Python
set PYTHON_CMD=
for %%i in (python py python3 python3.12 python3.11 python3.10 python3.9) do (
    where %%i >nul 2>&1
    if !errorlevel! == 0 (
        for /f "tokens=2" %%j in ('%%i --version 2^>^&1') do (
            set VERSION=%%j
            for /f "tokens=1,2 delims=." %%a in ("!VERSION!") do (
                if %%a GEQ 3 (
                    if %%b GEQ 9 (
                        set PYTHON_CMD=%%i
                        set PYTHON_VERSION=!VERSION!
                        goto :python_found
                    )
                )
            )
        )
    )
)

:python_found
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python 3.9+ is required but not found
    echo Please install Python 3.9 or higher from https://python.org
    echo Tried: python, py, python3, python3.12, python3.11, python3.10, python3.9
    exit /b 1
)
echo [OK] Python found: %PYTHON_CMD% (version %PYTHON_VERSION%)

REM Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed
    echo Please install Node.js from https://nodejs.org
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo [OK] Node.js found (%NODE_VERSION%)

REM Check npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm is not installed
    echo Please install npm (usually comes with Node.js)
    exit /b 1
)
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo [OK] npm found (%NPM_VERSION%)

REM Check git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] git is not installed
    echo Please install git from https://git-scm.com
    exit /b 1
)
echo [OK] git found

REM Clone or update repository
if exist "%INSTALL_DIR%" (
    echo Directory %INSTALL_DIR% already exists
    echo Updating existing repository...
    cd /d "%INSTALL_DIR%"
    git pull origin main
) else (
    echo Cloning repository to %INSTALL_DIR%...
    git clone "%REPO_URL%" "%INSTALL_DIR%"
    cd /d "%INSTALL_DIR%"
)

REM ============================================
REM PYTHON INDEXER SETUP
REM ============================================
echo Setting up Python indexer...

REM Set up virtual environment
set VENV_PATH=%INSTALL_DIR%\.venv
if not exist "%VENV_PATH%" (
    echo Creating Python virtual environment...
    %PYTHON_CMD% -m venv "%VENV_PATH%"
) else (
    echo [OK] Python virtual environment already exists
)

REM Set Python paths
set PYTHON_BIN=%VENV_PATH%\Scripts\python.exe
set PIP_BIN=%VENV_PATH%\Scripts\pip.exe

REM Install Python dependencies
echo Installing Python dependencies...
"%PIP_BIN%" install --upgrade pip
"%PIP_BIN%" install -r requirements.txt

REM Install claude_indexer package
echo Installing claude_indexer package...
"%PIP_BIN%" install -e .

REM Verify Python installation
"%PYTHON_BIN%" -c "import claude_indexer" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install claude_indexer package
    exit /b 1
)
echo [OK] claude_indexer package installed successfully

REM ============================================
REM NODE.JS MCP SERVER SETUP
REM ============================================
echo Setting up Node.js MCP server...

REM Install Node.js dependencies
echo Installing Node.js dependencies...
cd /d "%MCP_SERVER_DIR%"
npm install

REM Build TypeScript
echo Building TypeScript...
npm run build

REM Verify build
if not exist "%MCP_SERVER_DIR%\dist\index.js" (
    echo [ERROR] TypeScript build failed
    exit /b 1
)
echo [OK] MCP server built successfully

REM Return to root directory
cd /d "%INSTALL_DIR%"

REM ============================================
REM GLOBAL COMMAND WRAPPERS
REM ============================================
echo Setting up global command wrappers...

REM Create user bin directory
set BIN_DIR=%USERPROFILE%\bin
if not exist "%BIN_DIR%" (
    echo Creating bin directory: %BIN_DIR%
    mkdir "%BIN_DIR%"
)

REM Create wrapper batch files
set WRAPPER_PATH=%BIN_DIR%\claude-indexer.bat
set MCP_WRAPPER_PATH=%BIN_DIR%\mcp-qdrant-memory.bat

REM Create Python indexer wrapper
echo Creating Python indexer wrapper...
(
echo @echo off
echo REM Claude Code Memory Solution - Python Indexer Wrapper
echo.
echo set MEMORY_DIR=%INSTALL_DIR%
echo set PACKAGE_PATH=%INSTALL_DIR%\claude_indexer
echo set VENV_PATH=%VENV_PATH%
echo.
echo REM Check if files still exist
echo if not exist "%%PACKAGE_PATH%%" ^(
echo     echo [ERROR] claude_indexer package not found at %%PACKAGE_PATH%%
echo     echo The memory project may have been moved or deleted.
echo     exit /b 1
echo ^)
echo.
echo if not exist "%%VENV_PATH%%" ^(
echo     echo [ERROR] Virtual environment not found at %%VENV_PATH%%
echo     exit /b 1
echo ^)
echo.
echo REM Use absolute python path
echo set PYTHON_BIN=%%VENV_PATH%%\Scripts\python.exe
echo.
echo REM Run the indexer with all passed arguments
echo "%%PYTHON_BIN%%" -m claude_indexer %%*
) > "%WRAPPER_PATH%"

REM Create MCP server wrapper
echo Creating MCP server wrapper...
(
echo @echo off
echo REM Claude Code Memory Solution - MCP Server Wrapper
echo.
echo set MCP_SERVER_DIR=%MCP_SERVER_DIR%
echo.
echo REM Check if files still exist
echo if not exist "%%MCP_SERVER_DIR%%\dist\index.js" ^(
echo     echo [ERROR] MCP server not found at %%MCP_SERVER_DIR%%\dist\index.js
echo     echo The MCP server may have been moved or not built.
echo     exit /b 1
echo ^)
echo.
echo REM Run the MCP server with all passed arguments
echo node "%%MCP_SERVER_DIR%%\dist\index.js" %%*
) > "%MCP_WRAPPER_PATH%"

echo [OK] Python indexer wrapper created at %WRAPPER_PATH%
echo [OK] MCP server wrapper created at %MCP_WRAPPER_PATH%

REM ============================================
REM ENVIRONMENT SETUP
REM ============================================
echo Setting up environment configuration...

REM Create settings file from template if it doesn't exist
set SETTINGS_FILE=%INSTALL_DIR%\settings.txt
set TEMPLATE_FILE=%INSTALL_DIR%\settings.template.txt

if not exist "%SETTINGS_FILE%" (
    if exist "%TEMPLATE_FILE%" (
        echo Creating settings.txt from template...
        copy "%TEMPLATE_FILE%" "%SETTINGS_FILE%" >nul
        echo Please configure your API keys in %SETTINGS_FILE%
    )
)

REM Create MCP server .env file
set MCP_ENV_FILE=%MCP_SERVER_DIR%\.env
if not exist "%MCP_ENV_FILE%" (
    echo Creating MCP server .env file...
    (
    echo # Qdrant Configuration
    echo QDRANT_URL=http://localhost:6333
    echo QDRANT_API_KEY=
    echo QDRANT_COLLECTION_NAME=memory-project
    echo.
    echo # API Keys
    echo OPENAI_API_KEY=
    echo VOYAGE_API_KEY=
    ) > "%MCP_ENV_FILE%"
    echo Please configure your API keys in %MCP_ENV_FILE%
)

REM Check PATH
echo %PATH% | find /i "%BIN_DIR%" >nul
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] %BIN_DIR% is not in your PATH
    echo To use claude-indexer and mcp-qdrant-memory globally, add this to your PATH:
    echo %BIN_DIR%
    echo.
    echo You can do this by:
    echo 1. Press Win+R, type "sysdm.cpl", press Enter
    echo 2. Click "Environment Variables"
    echo 3. Under "User variables", select "Path" and click "Edit"
    echo 4. Click "New" and add: %BIN_DIR%
    echo 5. Click OK to save
    echo.
)

REM Final verification
if exist "%WRAPPER_PATH%" if exist "%MCP_WRAPPER_PATH%" (
    echo [OK] Windows installation successful!
    echo.
    echo Installation Summary:
    echo   OS: Windows
    echo   Python: %PYTHON_CMD% ^(%PYTHON_VERSION%^)
    echo   Repository: %INSTALL_DIR%
    echo   Python env: %VENV_PATH%
    echo   MCP server: %MCP_SERVER_DIR%
    echo   Bin directory: %BIN_DIR%
    echo   Python indexer: %WRAPPER_PATH%
    echo   MCP server: %MCP_WRAPPER_PATH%
    echo.
    echo Python Indexer Usage:
    echo   claude-indexer --project /path/to/project --collection project-name
    echo   claude-indexer --project . --collection current-project
    echo   claude-indexer --help
    echo.
    echo Setup Steps:
    echo 1. Start Qdrant database:
    echo    docker run -p 6333:6333 -v %%cd%%/qdrant_storage:/qdrant/storage qdrant/qdrant
    echo.
    echo 2. Configure API keys:
    echo    - Edit %SETTINGS_FILE%
    echo    - Edit %MCP_ENV_FILE%
    echo.
    echo 3. Test installation:
    echo    claude-indexer --help
    echo    mcp-qdrant-memory
    echo.
    echo [OK] Windows installation complete!
) else (
    echo [ERROR] Installation failed
    exit /b 1
)

endlocal