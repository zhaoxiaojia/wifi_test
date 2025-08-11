param(
  [string]$Interface = "Wi-Fi",
  [string]$CaseId = "case001",
  [string]$OutDir = "captures"
)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $OutDir "$CaseId`_$ts.pcapng"

# 仅抓管理/控制帧与 EAPOL
Start-Process dumpcap -ArgumentList @(
  "-i", "$Interface",
  "-b", "filesize:50000", "-b", "files:10",
  "-f", "'ether proto 0x888e or type mgt or type ctl'",
  "-w", "$out"
) -PassThru | ForEach-Object { $_.Id } | Set-Content -Path (Join-Path $OutDir ".pid")

$out | Set-Content -Path (Join-Path $OutDir ".latest")
Write-Host "[capture] started -> $out"
