# Shared helpers for Smart App Control / Mark-of-the-Web on local builds.

function Get-SmartAppControlState {
    try {
        $mp = Get-MpComputerStatus -ErrorAction Stop
        if ($mp.SmartAppControlState) {
            return [string]$mp.SmartAppControlState
        }
    } catch { }
    return "Unknown"
}

function Test-SmartAppControlBlocking {
    $state = Get-SmartAppControlState
    return $state -eq "On"
}

function Unblock-PathRecursive {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    $count = 0
    Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue
        $count++
    }
    return $count
}

function Open-SmartAppControlSettings {
    $uris = @(
        "ms-settings:windowsdefender-smartappcontrol",
        "windowsdefender://SmartAppControl",
        "windowsdefender://"
    )
    foreach ($uri in $uris) {
        try {
            Start-Process $uri -ErrorAction Stop
            return $true
        } catch { }
    }
    return $false
}

function Show-SmartAppControlHelp {
    param(
        [switch]$OpenSettings,
        [switch]$NonInteractive
    )

    $state = Get-SmartAppControlState
    Write-Host ""
    Write-Host "Smart App Control is: $state" -ForegroundColor $(if ($state -eq "On") { "Red" } else { "Yellow" })
    Write-Host ""
    Write-Host "While SAC is On, Windows blocks ALL unsigned .exe files (installer and app)." -ForegroundColor Yellow
    Write-Host "Scripts cannot bypass this. Turn SAC Off or sign the build." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Required fix for local builds:" -ForegroundColor Cyan
    Write-Host '  1. Windows Security -> App & browser control -> Smart App Control -> Off' -ForegroundColor White
    Write-Host "  2. Restart if prompted" -ForegroundColor White
    Write-Host "  3. Re-run: powershell -ExecutionPolicy Bypass -File build\Invoke-Installer.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Alternative after SAC is Off: build\Install-From-Dist.ps1 (skips setup.exe)" -ForegroundColor DarkGray
    Write-Host "Public releases: set VTU_AIDS_SIGN_PFX + VTU_AIDS_SIGN_PASSWORD, rebuild" -ForegroundColor DarkGray
    Write-Host ""

    $shouldOpen = $OpenSettings
    if (-not $NonInteractive -and -not $shouldOpen) {
        $open = Read-Host 'Open Smart App Control settings now? [Y/n]'
        $shouldOpen = ($open -eq "" -or $open -match "^[Yy]")
    }

    if ($shouldOpen) {
        if (Open-SmartAppControlSettings) {
            Write-Host "Opened Windows Security. Set Smart App Control to Off, then re-run the installer script." -ForegroundColor Green
        } else {
            Write-Host 'Open manually: Windows Security -> App & browser control -> Smart App Control' -ForegroundColor Yellow
        }
    }
}

function Assert-SmartAppControlAllowsUnsigned {
    param([switch]$OpenSettings)

    if (-not (Test-SmartAppControlBlocking)) { return }

    Show-SmartAppControlHelp -OpenSettings:$OpenSettings -NonInteractive
    throw "Smart App Control is On. Turn it Off in Windows Security, then try again."
}
