@echo off
REM Serves the downloaded Inside Hoi An build at http://127.0.0.1:4173
REM Port 4173 is used because port 3000 is taken by the POParsingApp Next.js server.
cd /d "%~dp0"
python serve.py 4173
