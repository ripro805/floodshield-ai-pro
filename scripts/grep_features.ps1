$path = "D:\KnowledgeVault\Project\FloodShield\frontend\app\dashboard\[district]\page.tsx"
$lines = Get-Content $path
$markers = @('DistrictName','DistrictNearestHospitals','DistrictHospitalMap','AssessmentPanel','useFullAssessmentV2','useAuth','useWeather','useWeeklyHistory')
foreach ($m in $markers) {
    $found = $false
    foreach ($l in $lines) { if ($l -like "*$m*") { $found = $true; break } }
    Write-Host ("{0,-30} {1}" -f $m, $found)
}
