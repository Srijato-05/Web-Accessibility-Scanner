@echo off
SETLOCAL EnableDelayedExpansion
TITLE SENTINEL SWARM - APEX PRIME (GPU)

:: 1. HARDWARE ENVIRONMENT SETUP
set CMAKE_ARGS="-DGGML_CUDA=on"
set FORCE_CMAKE=1
set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0
set PATH=%CUDA_PATH%\bin;%CUDA_PATH%\libnvvp;%PATH%

:: 2. DIRECTORY VERIFICATION
cd /d "%~dp0"
if not exist "models" mkdir "models"

:: 3. MODEL INTEGRITY CHECK
set MODEL_FILE=models\Qwen2.5-3B-Instruct-Q4_K_M.gguf
if not exist "%MODEL_FILE%" (
    echo [!] ERROR: Model %MODEL_FILE% not found.
    echo Please download it from HuggingFace and place it in the models folder.
    pause
    exit
)

:: 4. MEMORY PURGE (Optional: Clears GPU artifacts)
echo [*] Purging GPU Shaders...

:: 5. THE IGNITION
echo.
echo  ####################################################
echo  #         SENTINEL SWARM: APEX ACTIVATED         #
echo  #         HARDWARE: NVIDIA GTX 1650 (CUDA 13)    #
echo  ####################################################
echo.

:: We use 'uv run' to ensure the .venv is respected
uv run python main_agent_runner.py

if %ERRORLEVEL% NEQ 0 (
    echo [!] SWARM CRASHED WITH ERROR CODE %ERRORLEVEL%
    pause
)