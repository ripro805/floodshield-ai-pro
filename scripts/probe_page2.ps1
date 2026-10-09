try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:3000/dashboard/Feni -TimeoutSec 30
    Write-Host "First 500 chars:"
    Write-Host $r.Content.Substring(0, [Math]::Min(500, $r.Content.Length))
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
