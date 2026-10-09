$root = "D:\KnowledgeVault\Project\FloodShield"
$exclude = @('\.git\\', '\\node_modules\\', '\\.next\\', '\\.venv-py314\\', '\\.pytest_cache\\', '\\logs\\', '\\.puku\\', '\\FloodShieldAI_exports\\', '\\data\\')
Get-ChildItem -Recurse -File -Path $root -ErrorAction SilentlyContinue | Where-Object {
    $skip = $false
    foreach ($ex in $exclude) { if ($_.FullName -match $ex) { $skip = $true; break } }
    -not $skip -and $_.Length -gt 5MB
} | Select-Object -First 20 FullName, @{n='SizeMB';e={[math]::Round($_.Length/1MB,2)}} | Format-Table -AutoSize
