# Remove Mark-of-the-Web (Zone.Identifier) from the built app folder.
# Helps when the bundle was downloaded, copied from USB, or synced via OneDrive.
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir
)

$ErrorActionPreference = "SilentlyContinue"
if (-not (Test-Path $DistDir)) {
    Write-Host "Unblock-Dist: folder not found: $DistDir" -ForegroundColor Yellow
    exit 0
}

$count = 0
Get-ChildItem -LiteralPath $DistDir -Recurse -File | ForEach-Object {
    Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue
    $count++
}
Write-Host "Unblocked $count file(s) under $DistDir" -ForegroundColor DarkGray
