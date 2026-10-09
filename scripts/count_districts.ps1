$text = Get-Content "D:\KnowledgeVault\Project\FloodShield\frontend\lib\types.ts" -Raw
$idx = $text.IndexOf("BANGLADESH_DISTRICTS = [")
if ($idx -ge 0) {
    $end = $text.IndexOf("];", $idx)
    $block = $text.Substring($idx + "BANGLADESH_DISTRICTS = [".Length, $end - $idx - "BANGLADESH_DISTRICTS = [".Length)
    $items = $block -split "'," | ForEach-Object { $_.Trim() } | Where-Object { $_ -match "^[A-Z]" }
    Write-Host ("Frontend BANGLADESH_DISTRICTS count: " + $items.Count)
    foreach ($i in $items) { Write-Host "  $i" }
}
