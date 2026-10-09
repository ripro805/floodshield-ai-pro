$tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = "probe+x@example.com"; password = "Probe123!@#" } | ConvertTo-Json) -ErrorAction SilentlyContinue).access_token
if (-not $tok) {
    $email = "probe+" + (Get-Random) + "@example.com"
    $signup = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/signup -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#"; full_name = "Probe"; role = "admin" } | ConvertTo-Json)
    Write-Host "Signup: $($signup | ConvertTo-Json -Compress)"
    $tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#" } | ConvertTo-Json)).access_token
    Write-Host "Token len: $($tok.Length)"
}

$headers = @{ Authorization = "Bearer $tok" }

# /assessment/Feni
Write-Host "`n===== /assessment/Feni ====="
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/assessment/Feni" -Headers $headers -TimeoutSec 120
Write-Host ("is_operational=" + $r.is_operational + " generated_at=" + $r.generated_at)
foreach ($k in @("flood","water_level","overall_risk","disease_outbreak","disease_breakdown","forecast","satellite_extent","recommendation")) {
    $s = $r.$k
    if ($null -eq $s) {
        Write-Host ("  " + $k + ": <absent>")
        continue
    }
    $line = ("  " + $k + ": status=" + $s.status)
    if ($s.reason) { $line += " reason=" + $s.reason }
    if ($s.data_source) { $line += " data_source=" + $s.data_source }
    Write-Host $line
    if ($s.status -eq "ok" -and $s.data) {
        $preview = ($s.data | ConvertTo-Json -Compress -Depth 1)
        if ($preview.Length -gt 200) { $preview = $preview.Substring(0,200) + "..." }
        Write-Host ("    data: " + $preview)
    }
}

# /assessment/Dhaka
Write-Host "`n===== /assessment/Dhaka ====="
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/assessment/Dhaka" -Headers $headers -TimeoutSec 120
foreach ($k in @("flood","water_level","overall_risk","disease_outbreak","disease_breakdown","forecast","satellite_extent","recommendation")) {
    $s = $r.$k
    if ($null -eq $s) {
        Write-Host ("  " + $k + ": <absent>")
        continue
    }
    $line = ("  " + $k + ": status=" + $s.status)
    if ($s.reason) { $line += " reason=" + $s.reason }
    if ($s.data_source) { $line += " data_source=" + $s.data_source }
    Write-Host $line
    if ($s.status -eq "ok" -and $s.data) {
        $preview = ($s.data | ConvertTo-Json -Compress -Depth 1)
        if ($preview.Length -gt 200) { $preview = $preview.Substring(0,200) + "..." }
        Write-Host ("    data: " + $preview)
    }
}

# /assessment/Sylhet
Write-Host "`n===== /assessment/Sylhet ====="
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/assessment/Sylhet" -Headers $headers -TimeoutSec 120
foreach ($k in @("flood","water_level","overall_risk","disease_outbreak","disease_breakdown","forecast","satellite_extent","recommendation")) {
    $s = $r.$k
    if ($null -eq $s) { Write-Host ("  " + $k + ": <absent>"); continue }
    $line = ("  " + $k + ": status=" + $s.status)
    if ($s.reason) { $line += " reason=" + $s.reason }
    if ($s.data_source) { $line += " data_source=" + $s.data_source }
    Write-Host $line
}
