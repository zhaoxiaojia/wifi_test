param([string]$OutDir = "captures")
$pidFile = Join-Path $OutDir ".pid"
if (Test-Path $pidFile) {
  $pid = Get-Content $pidFile
  Stop-Process -Id $pid -ErrorAction SilentlyContinue
  Remove-Item $pidFile -Force
  Write-Host "[capture] stopped (pid=$pid)"
} else {
  Write-Host "[capture] no running capture found."
}
$latest = Join-Path $OutDir ".latest"
if (Test-Path $latest) {
  Write-Host "[capture] pcap -> $(Get-Content $latest)"
}
