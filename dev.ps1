$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Install Python requirements first; see README.md.' }
$api = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $repo -WindowStyle Hidden -PassThru
$ui = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','5173' -WorkingDirectory (Join-Path $repo 'frontend') -WindowStyle Hidden -PassThru
Write-Host "WasteWise VN: http://127.0.0.1:5173 (API process $($api.Id), UI launcher $($ui.Id))"
