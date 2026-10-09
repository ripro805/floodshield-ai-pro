Set-Location d:\KnowledgeVault\Project\FloodShield\frontend
$out = npx tsc --noEmit --project tsconfig.json 2>&1
$out | Out-File -FilePath d:\KnowledgeVault\Project\FloodShield\frontend\_tsc.txt -Encoding utf8
Write-Host "rc=$LASTEXITCODE"
$out | Select-Object -Last 30
