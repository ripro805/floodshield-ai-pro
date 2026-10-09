$root = "D:\KnowledgeVault\Project\FloodShield"
$exclude = @('\.git\\', '\\node_modules\\', '\\.next\\', '\\.venv-py314\\', '\\.pytest_cache\\', '\\logs\\', '\\.puku\\', '\\FloodShieldAI_exports\\', '\\data\\', '\\backend\\data\\')
Get-ChildItem -Recurse -File -Path $root -ErrorAction SilentlyContinue | ForEach-Object {
    $path = $_.FullName
    $skip = $false
    foreach ($ex in $exclude) { if ($path -match $ex) { $skip = $true; break } }
    if ($skip) { return }
    $name = $_.Name.ToLower()
    if ($name -match '\.env' -or $name -match 'ee_service_account' -or $name -match 'token' -or $name -match 'credential' -or $name -match 'private.*key' -or $name -match '\.pem$') {
        Write-Host $path
    }
}
