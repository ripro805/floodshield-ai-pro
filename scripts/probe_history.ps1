$tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = "probe+y@example.com"; password = "Probe123!@#" } | ConvertTo-Json) -ErrorAction SilentlyContinue).access_token
if (-not $tok) {
    $email = "probe+" + (Get-Random) + "@example.com"
    $null = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/signup -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#"; full_name = "Probe"; role = "admin" } | ConvertTo-Json)
    $tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#" } | ConvertTo-Json)).access_token
}
$headers = @{ Authorization = "Bearer $tok" }
foreach ($d in @("Feni","Dhaka","Sylhet")) {
    $r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/history/weekly/$d" -Headers $headers -TimeoutSec 30
    Write-Host "$d weeks=$($r.weeks.Count) source=$($r.source) first=$($r.weeks[0].week_ending) last=$($r.weeks[-1].week_ending)"
}
