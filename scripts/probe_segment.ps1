$tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = "probe+w@example.com"; password = "Probe123!@#" } | ConvertTo-Json) -ErrorAction SilentlyContinue).access_token
if (-not $tok) {
    $email = "probe+" + (Get-Random) + "@example.com"
    $null = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/signup -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#"; full_name = "Probe"; role = "admin" } | ConvertTo-Json)
    $tok = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login -ContentType "application/json" -Body (@{ email = $email; password = "Probe123!@#" } | ConvertTo-Json)).access_token
}
$headers = @{ Authorization = "Bearer $tok" }
Write-Host "===== ingest + segment Feni ====="
$ingest = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/satellite/ingest?district=Feni" -Headers $headers -TimeoutSec 60
$chip = $ingest.pixel_values
Write-Host ("chip shape=" + ($ingest.shape -join ",") + " source=" + $ingest.source + " pixels_count=" + $chip.Count)
# Compute min/max of VV band (channel 0)
$minV = [double]::PositiveInfinity
$maxV = [double]::NegativeInfinity
$sumV = 0.0
$countV = 0
foreach ($row in $chip) {
    foreach ($px in $row) {
        $v = [double]$px[0]
        if ($v -lt $minV) { $minV = $v }
        if ($v -gt $maxV) { $maxV = $v }
        $sumV += $v
        $countV += 1
    }
}
Write-Host ("VV band min=" + $minV + " max=" + $maxV + " mean=" + ($sumV / $countV))
# Reconstruct the body the way ingestAndSegmentDistrict does (pixel_values as the bare list)
$body = $chip
$seg = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/satellite/segment" -Headers $headers -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 6) -TimeoutSec 240
Write-Host ("segment result=" + ($seg | ConvertTo-Json -Compress))
