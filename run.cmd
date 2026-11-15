@echo off
cd /d "%~dp0"
uv run python -m fusion_collection %*
