Set-Location "D:\KnowledgeVault\Project\FloodShield"
$files = git add -A --dry-run 2>&1 | Where-Object { $_ -match "^add '" } | ForEach-Object {
    $name = $_ -replace "^add '", "" -replace "'$", ""
    [pscustomobject]@{ Name = $name; Full = (Resolve-Path $name -ErrorAction SilentlyContinue).Path }
}
$count = ($files | Measure-Object).Count
Write-Host "Files to be committed: $count"
$total = 0
foreach ($f in $files) {
    if ($f.Full -and (Test-Path $f.Full)) {
        $size = (Get-Item $f.Full -ErrorAction SilentlyContinue).Length
        $total += $size
    }
}
Write-Host ("Total size: {0:N1} MB" -f ($total / 1MB))
Write-Host "---"
Write-Host "Largest 10 files:"
$files | ForEach-Object {
    if ($_.Full -and (Test-Path $_.Full)) { $_.Size = (Get-Item $_.Full).Length } else { $_.Size = 0 }
} | Sort-Object Size -Descending | Select-Object -First 10 Name, @{n='MB';e={[math]::Round($_.Size/1MB,2)}} | Format-Table -AutoSize
Write-Host "---"
Write-Host "Sensitive patterns check:"
git add -A --dry-run 2>&1 | Select-String -Pattern '(\.env$|ee_service_account|\.env\.local|credentials\.csv|scratch_tokens|\.pem$|private.*\.key)' | Select-Object -First 20
Write-Host "---"
Write-Host "Any *.bak files:"
git add -A --dry-run 2>&1 | Where-Object { $_ -match "\.bak" } | Select-Object -First 20
