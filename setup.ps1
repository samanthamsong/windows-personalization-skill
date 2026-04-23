<#
.SYNOPSIS
    One-command setup for the Windows Personalization Skill.
.DESCRIPTION
    Checks prerequisites, installs Python dependencies, builds the .NET driver,
    copies it to the canonical install path, registers for package identity,
    installs the skill to ~/.copilot/skills/ for Copilot CLI discovery,
    and verifies everything works.

    Run from the repo root:
        .\setup.ps1

    First run may require admin for certificate trust:
        Start-Process powershell -Verb RunAs -ArgumentList "-File $PWD\setup.ps1"
#>

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Windows Personalization Skill - Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Check prerequisites
Write-Host "`nStep 1: Checking prerequisites..." -ForegroundColor Yellow

$missing = @()

# .NET SDK
$dotnetVer = $null
try { $dotnetVer = (dotnet --version 2>$null) } catch {}
if ($dotnetVer -and $dotnetVer -match "^[89]\.|^[1-9]\d+\.") {
    Write-Host "  dotnet SDK: $dotnetVer" -ForegroundColor Green
} else {
    $missing += ".NET 9 SDK (winget install Microsoft.DotNet.SDK.9)"
}

# Python
$pythonVer = $null
try { $pythonVer = (python --version 2>$null) } catch {}
if ($pythonVer -and $pythonVer -match "3\.\d+") {
    Write-Host "  Python: $pythonVer" -ForegroundColor Green
} else {
    $missing += "Python 3.10+ (winget install Python.Python.3.12)"
}

# WinAppCLI
$winappVer = $null
try { $winappVer = (winapp --version 2>$null) } catch {}
if ($winappVer) {
    Write-Host "  WinAppCLI: $winappVer" -ForegroundColor Green
} else {
    $missing += "WinAppCLI (winget install Microsoft.WinAppCli)"
}

# Developer Mode
$devMode = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -ErrorAction SilentlyContinue
if ($devMode -and $devMode.AllowDevelopmentWithoutDevLicense -eq 1) {
    Write-Host "  Developer Mode: enabled" -ForegroundColor Green
} else {
    Write-Host "  Developer Mode: not enabled (recommended)" -ForegroundColor Yellow
    Write-Host "    Enable in Settings -> System -> For developers -> Developer Mode" -ForegroundColor Yellow
}

if ($missing.Count -gt 0) {
    Write-Host "`n  Missing prerequisites:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    Write-Error "Please install the missing prerequisites and re-run setup."
    exit 1
}

# Step 2: Install Python dependencies
Write-Host "`nStep 2: Installing Python dependencies..." -ForegroundColor Yellow
pip install --quiet Pillow requests mss 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Core dependencies installed." -ForegroundColor Green
} else {
    Write-Warning "  pip install had issues. Effects may still work."
}

# Optional Spotify dependencies
Write-Host "  Installing optional Spotify dependencies..." -ForegroundColor Yellow
pip install --quiet spotipy pycaw comtypes numpy 2>$null
Write-Host "  Spotify dependencies installed (use 'python modules/spotify/auth.py' to authenticate)." -ForegroundColor Green

# Step 3: Build the .NET driver
Write-Host "`nStep 3: Building Dynamic Lighting driver..." -ForegroundColor Yellow
$slnPath = Join-Path $PSScriptRoot "modules\dynamic-lighting\DynamicLightingDriver.sln"
dotnet build $slnPath -c Debug --verbosity quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed. Check .NET SDK installation."
    exit 1
}
Write-Host "  Build succeeded." -ForegroundColor Green

# Step 4: Copy to canonical install path
Write-Host "`nStep 4: Installing driver to %LocalAppData%\DynamicLightingDriver..." -ForegroundColor Yellow
$InstallDir = Join-Path $env:LOCALAPPDATA "DynamicLightingDriver"
$BuildOutput = Join-Path $PSScriptRoot "modules\dynamic-lighting\src\DynamicLightingDriver\bin\Debug\net9.0-windows10.0.26100.0"

if (-not (Test-Path $InstallDir)) {
    New-Item $InstallDir -ItemType Directory | Out-Null
}
Copy-Item "$BuildOutput\*" $InstallDir -Recurse -Force
Write-Host "  Installed to: $InstallDir" -ForegroundColor Green

# Step 5: Register for package identity
Write-Host "`nStep 5: Registering for package identity..." -ForegroundColor Yellow
$registerScript = Join-Path $PSScriptRoot "modules\dynamic-lighting\src\DynamicLightingDriver\Package\Register-AmbientLighting.ps1"
& $registerScript

# Step 6: Install as Copilot personal skill
Write-Host "`nStep 6: Installing as Copilot personal skill..." -ForegroundColor Yellow
$SkillsDir = Join-Path $env:USERPROFILE ".copilot\skills"
$SkillLink = Join-Path $SkillsDir "windows-personalization"

if (-not (Test-Path $SkillsDir)) {
    New-Item $SkillsDir -ItemType Directory -Force | Out-Null
    Write-Host "  Created: $SkillsDir" -ForegroundColor Green
}

if (Test-Path $SkillLink) {
    $existing = Get-Item $SkillLink -Force
    if ($existing.LinkType -eq "Junction" -or $existing.LinkType -eq "SymbolicLink") {
        $target = $existing.Target
        if ($target -eq $PSScriptRoot) {
            Write-Host "  Skill already linked to this repo." -ForegroundColor Green
        } else {
            Write-Host "  Existing skill link points to: $target" -ForegroundColor Yellow
            Write-Host "  Updating to point to: $PSScriptRoot" -ForegroundColor Yellow
            Remove-Item $SkillLink -Force
            New-Item -ItemType Junction -Path $SkillLink -Target $PSScriptRoot | Out-Null
            Write-Host "  Skill link updated." -ForegroundColor Green
        }
    } else {
        Write-Host "  WARNING: $SkillLink already exists and is not a link." -ForegroundColor Yellow
        Write-Host "  Please remove it manually and re-run setup, or create a junction:" -ForegroundColor Yellow
        Write-Host "    cmd /c mklink /J `"$SkillLink`" `"$PSScriptRoot`"" -ForegroundColor Yellow
    }
} else {
    New-Item -ItemType Junction -Path $SkillLink -Target $PSScriptRoot | Out-Null
    Write-Host "  Installed: $SkillLink -> $PSScriptRoot" -ForegroundColor Green
}

# Step 7: Verify
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ExePath = Join-Path $InstallDir "DynamicLightingDriver.exe"
$pkg = Get-AppxPackage -Name "DynamicLightingDriver" -ErrorAction SilentlyContinue

$allGood = $true

if (Test-Path $ExePath) {
    Write-Host "  Driver EXE:    OK ($ExePath)" -ForegroundColor Green
} else {
    Write-Host "  Driver EXE:    MISSING" -ForegroundColor Red
    $allGood = $false
}

if ($pkg -and $pkg.Status -eq "Ok") {
    Write-Host "  Package:       OK ($($pkg.PackageFullName))" -ForegroundColor Green
} else {
    Write-Host "  Package:       NOT REGISTERED" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path (Join-Path $SkillLink "SKILL.md")) {
    Write-Host "  Copilot Skill: OK ($SkillLink)" -ForegroundColor Green
} else {
    Write-Host "  Copilot Skill: NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if ($allGood) {
    Write-Host "`n  Setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  IMPORTANT: Go to Settings -> Personalization -> Dynamic Lighting" -ForegroundColor Yellow
    Write-Host "  -> Background light control and ensure 'Dynamic Lighting Driver'" -ForegroundColor Yellow
    Write-Host "  is BELOW 'Dynamic Lighting Background Controller' in priority." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Skill installed to: $SkillLink" -ForegroundColor Cyan
    Write-Host "  If you move this repo, re-run setup.ps1 to update the link." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Try it:" -ForegroundColor Cyan
    Write-Host "    python modules/dynamic-lighting/lighting.py list-devices"
    Write-Host "    python modules/dynamic-lighting/lighting.py set-color red"
    Write-Host "    python modules/dynamic-lighting/lighting.py run-effect koi-fish"
} else {
    Write-Host "`n  Setup had issues. See errors above." -ForegroundColor Red
    Write-Host "  Try running as admin: Start-Process powershell -Verb RunAs -ArgumentList '-File $PSCommandPath'" -ForegroundColor Yellow
}
