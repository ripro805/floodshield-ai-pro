$tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = "probe+z@example.com"; password = "Probe123!@#" } | ConvertTo-Json) -ErrorAction SilentlyContinue).access_token
if (-not $tok) {
    $email = "probe+" + (Get-Random) + "@example.com"
    $null = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/signup -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#"; full_name = "Probe"; role = "admin" } | ConvertTo-Json)
    $tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#" } | ConvertTo-Json)).access_token
}
$headers = @{ Authorization = "Bearer $tok" }
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/satellite/flood-extent" -Headers $headers -TimeoutSec 30
Write-Host ("available_districts: " + ($r.available_districts -join ", "))
foreach ($d in $r.available_districts) {
    Write-Host "`n--- $d ---"
    try {
        $fe = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/satellite/flood-extent/$d" -Headers $headers -TimeoutSec 30
        Write-Host ("event_label=" + $fe.event_label)
        Write-Host ("geojson type=" + $fe.geojson.type)
    } catch {
        Write-Host ("error: " + $_.Exception.Message)
    }
}
