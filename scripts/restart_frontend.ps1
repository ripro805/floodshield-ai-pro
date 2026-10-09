Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Set-Location "D:\KnowledgeVault\Project\FloodShield\frontend"
$logDir = "D:\KnowledgeVault\Project\FloodShield\logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir "next_assessment.log"
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npx next dev -p 3000" -WorkingDirectory "D:\KnowledgeVault\Project\FloodShield\frontend" -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden -PassThru
Write-Host "Started. log=$log"
