$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Install Python requirements first; see README.md.' }
$apiPort = '8001'
$uiPort = '5175'
$env:VITE_API_URL = "http://127.0.0.1:$apiPort"
$env:CORS_ORIGINS = "http://localhost:$uiPort,http://127.0.0.1:$uiPort,http://localhost:5174,http://127.0.0.1:5174"
$api = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',$apiPort -WorkingDirectory $repo -WindowStyle Hidden -PassThru
$ui = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port',$uiPort -WorkingDirectory (Join-Path $repo 'frontend') -WindowStyle Hidden -PassThru
Write-Host "WasteWise VN: http://127.0.0.1:$uiPort (FastAPI: http://127.0.0.1:$apiPort, API process $($api.Id), UI launcher $($ui.Id))"
