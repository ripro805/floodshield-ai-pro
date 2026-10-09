try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:3000/dashboard/Feni -TimeoutSec 30
    Write-Host "Status: $($r.StatusCode)"
    $body = $r.Content
    Write-Host "Body length: $($body.Length)"
    $markers = @('AssessmentPanel','Full Assessment','Disease Outbreak Risk','Disease Breakdown','7 / 14-day Forecast','Satellite Flood Extent','Run Segmentation','Re-run')
    foreach ($m in $markers) {
        $present = $body.Contains($m)
        Write-Host ("  {0,-30} {1}" -f $m, $present)
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
