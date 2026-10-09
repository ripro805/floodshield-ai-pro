$src = "D:\KnowledgeVault\Project\FloodShield"
$dst = "D:\KnowledgeVault\FloodShield_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
Copy-Item -Path $src -Destination $dst -Recurse -Force
Write-Host "Backup created at $dst"
$srcSize = (Get-ChildItem -Path $src -Recurse -File | Measure-Object -Property Length -Sum).Sum
$dstSize = (Get-ChildItem -Path $dst -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ("Source size: {0} bytes" -f $srcSize)
Write-Host ("Dest   size: {0} bytes" -f $dstSize)
