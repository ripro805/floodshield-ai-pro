Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Set-Location "D:\KnowledgeVault\Project\FloodShield\backend"
$logDir = "D:\KnowledgeVault\Project\FloodShield\logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir "uvicorn_assessment.log"
$proc = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden -PassThru
Write-Host "PID=$($proc.Id) log=$log"
Start-Sleep -Seconds 6
Get-Content $log -Tail 30
