<#
.SYNOPSIS
    Registers the Dynamic Lighting Driver as an ambient lighting app.
.DESCRIPTION
    This script:
    1. Builds the .NET project
    2. Copies the build output to a canonical install path (%LocalAppData%\DynamicLightingDriver)
    3. Registers the app via loose AppX registration (requires Developer Mode)
    After registration, the app appears in Settings > Personalization > Dynamic Lighting > Background light control
    and can control lighting in the background without needing foreground focus.
.NOTES
    Requires Developer Mode enabled (Settings > System > For developers).
    To unregister: Get-AppxPackage *DynamicLightingDriver* | Remove-AppxPackage
#>

param(
    [string]$Configuration = "Debug"
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$CsprojPath = Join-Path $ProjectDir "DynamicLightingDriver.csproj"
$PackageDir = Join-Path $ProjectDir "Package"
$ManifestPath = Join-Path $PackageDir "AppxManifest.xml"

# Determine build output directory
$Tfm = "net9.0-windows10.0.26100.0"
$BuildOutputDir = Join-Path $ProjectDir "bin\$Configuration\$Tfm"

# Canonical install path - all scripts reference this location
$InstallDir = Join-Path $env:LOCALAPPDATA "DynamicLightingDriver"

# Determine architecture
$Arch = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq [System.Runtime.InteropServices.Architecture]::Arm64) { "arm64" } else { "x64" }

Write-Host "=== Dynamic Lighting Driver - Registration ===" -ForegroundColor Cyan

# Step 1: Build
Write-Host "`nStep 1: Building project..." -ForegroundColor Yellow
dotnet build $CsprojPath -c $Configuration
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}
Write-Host "  Build succeeded." -ForegroundColor Green

# Step 2: Copy build output to canonical install path
Write-Host "`nStep 2: Installing to $InstallDir..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item $InstallDir -ItemType Directory | Out-Null
}
Copy-Item "$BuildOutputDir\*" $InstallDir -Recurse -Force
Write-Host "  Copied build output to install directory." -ForegroundColor Green

# Step 3: Unregister previous version if present
Write-Host "`nStep 3: Checking for existing registration..." -ForegroundColor Yellow
$existing = Get-AppxPackage -Name "DynamicLightingDriver" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removing existing package..." -ForegroundColor Yellow
    Remove-AppxPackage $existing.PackageFullName
    Start-Sleep -Seconds 2
    Write-Host "  Removed." -ForegroundColor Green
} else {
    Write-Host "  No existing registration found." -ForegroundColor Green
}

$oldPkg = Get-AppxPackage -Name "DynamicLightingMcp" -ErrorAction SilentlyContinue
if ($oldPkg) {
    Write-Host "  Removing old DynamicLightingMcp package..." -ForegroundColor Yellow
    Remove-AppxPackage $oldPkg.PackageFullName
    Start-Sleep -Seconds 2
    Write-Host "  Removed old package." -ForegroundColor Green
}

# Step 4: Register via loose AppX registration (requires Developer Mode)
Write-Host "`nStep 4: Registering package (loose registration)..." -ForegroundColor Yellow
$LooseDir = Join-Path $env:LOCALAPPDATA "DynamicLightingDriver_Layout"
if (Test-Path $LooseDir) { Remove-Item $LooseDir -Recurse -Force }
New-Item $LooseDir -ItemType Directory | Out-Null

# Copy and patch manifest with correct architecture
$ManifestContent = Get-Content $ManifestPath -Raw
$ManifestContent = $ManifestContent -replace 'ProcessorArchitecture="[^"]*"', "ProcessorArchitecture=`"$Arch`""
Set-Content "$LooseDir\AppxManifest.xml" $ManifestContent -Encoding UTF8
Write-Host "  Patched manifest ProcessorArchitecture to $Arch" -ForegroundColor Green

Copy-Item (Join-Path $PackageDir "Assets") "$LooseDir\Assets" -Recurse
if (Test-Path (Join-Path $PackageDir "public")) {
    Copy-Item (Join-Path $PackageDir "public") "$LooseDir\public" -Recurse
}
Copy-Item (Join-Path $InstallDir "DynamicLightingDriver.exe") "$LooseDir\" -Force

try {
    Add-AppxPackage -Register "$LooseDir\AppxManifest.xml" -ExternalLocation $InstallDir
    Write-Host "  Registration succeeded!" -ForegroundColor Green
} catch {
    Write-Error "Registration failed. Ensure Developer Mode is enabled: Settings > System > For developers > Developer Mode (ON)."
    exit 1
}

# Step 5: Verify
Write-Host "`nStep 5: Verifying registration..." -ForegroundColor Yellow
$pkg = Get-AppxPackage -Name "DynamicLightingDriver"
if ($pkg) {
    Write-Host "  Package: $($pkg.PackageFullName)" -ForegroundColor Green
    Write-Host "  Status:  $($pkg.Status)" -ForegroundColor Green
    Write-Host "  SignatureKind: $($pkg.SignatureKind)" -ForegroundColor Green
} else {
    Write-Warning "  Package not found after installation. Check for errors above."
}

# Verify the driver can actually launch
Write-Host "`nStep 6: Verifying driver launches..." -ForegroundColor Yellow
$ExePath = Join-Path $InstallDir "DynamicLightingDriver.exe"
if (Test-Path $ExePath) {
    Write-Host "  Driver EXE found at: $ExePath" -ForegroundColor Green
} else {
    Write-Warning "  Driver EXE not found at expected path: $ExePath"
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host "Your app should now appear in:"
Write-Host "  Settings -> Personalization -> Dynamic Lighting -> Background light control"
Write-Host ""
Write-Host "IMPORTANT: Move 'Dynamic Lighting Driver' to the TOP of the list,"
Write-Host "ABOVE 'Dynamic Lighting Background Controller', for ambient background control."
Write-Host ""
Write-Host "Driver installed to: $InstallDir"
Write-Host "To unregister: Get-AppxPackage *DynamicLightingDriver* | Remove-AppxPackage"
