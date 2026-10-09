Start-Sleep -Seconds 8
$districts = @('Feni','Dhaka','Barishal','Bogura','Sylhet','Cumilla','Cox''s Bazar','Comilla','Bhola','Khulna')
foreach ($d in $districts) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3000/dashboard/$d" -TimeoutSec 30
        Write-Host "$d -> $($r.StatusCode)"
    } catch {
        Write-Host "$d -> error: $($_.Exception.Message)"
    }
}
