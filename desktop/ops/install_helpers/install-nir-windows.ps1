$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

$checksumFile = Join-Path $dir "desktop-release-sha256-windows.txt"
if (-not (Test-Path $checksumFile)) {
  throw "Missing checksum file: $checksumFile"
}

Write-Host "Verifying Windows installer checksums..."
$checksumLines = Get-Content -Path $checksumFile | Where-Object { $_.Trim() -ne "" }
$verifiedInstallerEntries = 0
foreach ($line in $checksumLines) {
  $parts = $line -split "\s+", 2
  if ($parts.Count -lt 2) { throw "Invalid checksum line: $line" }
  $expected = $parts[0].ToLower()
  $fileName = $parts[1].TrimStart("*").Trim()
  if ($fileName -notmatch "\.(exe|msi)$") { continue }
  $target = Join-Path $dir $fileName
  if (-not (Test-Path $target)) {
    throw "Missing installer listed in checksum file: $fileName"
  }
  $actual = (Get-FileHash -Algorithm SHA256 -Path $target).Hash.ToLower()
  if ($actual -ne $expected) {
    throw "Checksum mismatch for $fileName"
  }
  $verifiedInstallerEntries++
}
if ($verifiedInstallerEntries -lt 1) {
  throw "No Windows installer entries found in checksum file."
}

$exe = Get-ChildItem -Path $dir -Filter *.exe | Select-Object -First 1
if ($exe) {
  Write-Host "Launching installer: $($exe.FullName)"
  Start-Process -FilePath $exe.FullName
  exit 0
}

$msi = Get-ChildItem -Path $dir -Filter *.msi | Select-Object -First 1
if ($msi) {
  Write-Host "Launching installer: $($msi.FullName)"
  Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$($msi.FullName)`""
  exit 0
}

throw "No Windows installer found (.exe or .msi)."
