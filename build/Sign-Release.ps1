# Optional Authenticode signing (removes Smart App Control / SmartScreen blocks for most users).
# Set env vars before build:
#   VTU_AIDS_SIGN_PFX = path to .pfx
#   VTU_AIDS_SIGN_PASSWORD = certificate password
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string[]]$ExtraFiles = @()
)

$Dist = Join-Path $InstallRoot "dist\VTU AIDS"
if (-not (Test-Path $Dist)) {
    Write-Host "No dist folder to sign: $Dist" -ForegroundColor Yellow
    exit 0
}

$pfx = $env:VTU_AIDS_SIGN_PFX
if (-not $pfx) {
    Write-Host "Skip signing (set VTU_AIDS_SIGN_PFX to sign the release)." -ForegroundColor DarkGray
    exit 0
}

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    throw "signtool.exe not found. Install Windows SDK or Visual Studio Build Tools."
}

$signArgs = @("sign", "/fd", "SHA256", "/f", $pfx, "/tr", "http://timestamp.digicert.com", "/td", "SHA256")
if ($env:VTU_AIDS_SIGN_PASSWORD) {
    $signArgs += @("/p", $env:VTU_AIDS_SIGN_PASSWORD)
}

$targets = Get-ChildItem -LiteralPath $Dist -Recurse -File -Include *.exe, *.dll |
    Where-Object { $_.FullName -notmatch '\\_bootloader\\' }
$signed = 0
foreach ($file in $targets) {
    $existing = Get-AuthenticodeSignature -FilePath $file.FullName
    if ($existing.Status -eq "Valid" -and $existing.SignerCertificate.Subject -match "Python Software Foundation") {
        continue
    }
    & $signtool.Source @signArgs $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "signtool failed on $($file.Name) with exit $LASTEXITCODE" }
    $signed++
}
foreach ($extra in $ExtraFiles) {
    if (-not (Test-Path $extra)) { continue }
    $existing = Get-AuthenticodeSignature -FilePath $extra
    if ($existing.Status -eq "Valid") { continue }
    & $signtool.Source @signArgs $extra
    if ($LASTEXITCODE -ne 0) { throw "signtool failed on $extra with exit $LASTEXITCODE" }
    $signed++
    Write-Host "Signed $extra" -ForegroundColor Green
}

Write-Host "Signed $signed binary file(s) (dist + extras)" -ForegroundColor Green
