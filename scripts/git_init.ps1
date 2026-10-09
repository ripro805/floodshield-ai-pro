Set-Location "D:\KnowledgeVault\Project\FloodShield"
git init
git config user.email "dev@floodshield.local"
git config user.name "FloodShield Dev"
try { git branch -M main } catch {}
Write-Host "--- status ---"
git status -s | Select-Object -First 30
