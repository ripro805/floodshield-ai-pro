Set-Location "D:\KnowledgeVault\Project\FloodShield"
git add -A --dry-run 2>&1 | Select-Object -First 50
Write-Host "---"
Write-Host "Total files staged in dry run: $(git add -A --dry-run 2>&1 | Measure-Object).Count"
Write-Host "---"
Write-Host "Any sensitive patterns:"
git add -A --dry-run 2>&1 | Select-String -Pattern '(\.env|ee_service|credentials|tokens|test_users_credentials)' | Select-Object -First 20
