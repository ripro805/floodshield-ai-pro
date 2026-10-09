Start-Sleep -Seconds 8
foreach ($d in 'Feni','Dhaka','Sylhet') {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3000/dashboard/$d" -TimeoutSec 30
        Write-Host "$d -> $($r.StatusCode) (length=$($r.Content.Length))"
    } catch {
        Write-Host "$d -> error: $($_.Exception.Message)"
    }
}
