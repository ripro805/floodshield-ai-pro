Set-Location "D:\KnowledgeVault\Project\FloodShield"
Remove-Item -Path "backend\app\routers\disease_breakdown.py.bak" -ErrorAction SilentlyContinue

$names = git add -A --dry-run 2>&1 | Where-Object { $_ -match "^add '" } | ForEach-Object {
    $_.Substring(5).TrimEnd("'") -replace "^'", ""
}
$count = ($names | Measure-Object).Count
Write-Host "Files to be committed: $count"
$total = 0
$sizes = @()
foreach ($n in $names) {
    if ($n -and (Test-Path $n)) {
        $s = (Get-Item $n).Length
        $total += $s
        $sizes += [pscustomobject]@{ Name = $n; Size = $s }
    }
}
Write-Host ("Total size: {0:N2} MB" -f ($total / 1MB))
Write-Host "---"
Write-Host "Top 15 largest files:"
$sizes | Sort-Object Size -Descending | Select-Object -First 15 | ForEach-Object { "{0,10:N1} KB  {1}" -f ($_.Size/1KB), $_.Name } | Write-Host
Write-Host "---"
Write-Host "Sensitive patterns check (should be empty):"
$names | Where-Object { $_ -match '(\.env$|\.env\.local|ee_service_account|credentials\.csv|scratch_tokens|\.pem$|private.*\.key)' } | ForEach-Object { Write-Host "  $($_)" }
