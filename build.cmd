@echo off
setlocal
cd /d "%~dp0"
rem Run in an x64 MSVC developer command prompt with CMake, Ninja and Qt available.
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release %*
if errorlevel 1 exit /b 1
cmake --build build --parallel 4
exit /b %errorlevel%
