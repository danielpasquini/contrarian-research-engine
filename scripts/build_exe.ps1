# Build Standalone Windows Executable (.exe) for Contrarian Engine
$ErrorActionPreference = "Stop"
uv run pyinstaller --noconsole --onefile --name="Contrarian Engine" --icon="favicon.ico" --add-data "favicon.ico;." --add-data "favicon.png;." --add-data "dashboard;dashboard" --add-data "src;src" --add-data ".env;." app.py
if (Test-Path ".env") { Copy-Item ".env" -Destination "dist\.env" -Force }
