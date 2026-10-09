Set-Location "D:\KnowledgeVault\Project\FloodShield"
git add -A
$status = git status -s | Measure-Object
Write-Host "Staged files: $($status.Count)"
Write-Host "---"
git diff --cached --stat | Select-Object -Last 5
Write-Host "---"
git commit -m "Initial commit: FloodShield AI platform

- 64-district Bangladesh flood risk + health platform
- Backend: FastAPI + SQLAlchemy + asyncpg; Auth (citizen/health_worker/hospital/ngo/admin)
- Routers: assessment, flood, forecast, disease, disease_breakdown, hospitals, history, chatbot, admin
- Sentinel-1 satellite flood extent pipeline (real exports + synthetic placeholders for 64 districts)
- Disease outbreak risk model + breakdown breakdown
- RAG chatbot (HuggingFace + OpenAI compatible)
- Hospital inventory management
- Reference data: districts, rivers, weather stations
- Frontend: Next.js 14 app router with district dashboard, map, chatbot widget
- Maps: Leaflet (AssessmentMap + DistrictRiskMap) with Bangladesh bounds and district zoom
- Docker compose for local + production" 2>&1 | Select-Object -Last 10
Write-Host "---"
git log --oneline -3
