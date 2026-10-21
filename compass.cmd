@echo off
rem Development shim: run Compass from this checkout without installing.
set "PYTHONPATH=%~dp0python"
python -m compass.cli %*
