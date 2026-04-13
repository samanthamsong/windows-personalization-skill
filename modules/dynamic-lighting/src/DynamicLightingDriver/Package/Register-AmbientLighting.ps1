<#
.SYNOPSIS
    Registers the Dynamic Lighting Driver as an ambient lighting app using a signed MSIX package.
.DESCRIPTION
    This script:
    1. Builds the .NET project
    2. Creates a self-signed certificate (if needed) and imports it to Trusted People
    3. Creates and signs a .msix package
    4. Installs the signed package with external content pointing to build output
    After registration, the app appears in Settings > Personalization > Dynamic Lighting > Background light control
    and can control lighting in the background without needing foreground focus.
.NOTES
    Requires elevation (admin) for certificate import to LocalMachine\TrustedPeople.
    To unregister: Get-AppxPackage *DynamicLightingDriver* | Remove-AppxPackage
#>

param(
    [string]$Configuration = "Debug"
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ProjectDir
$CsprojPath = Join-Path $ProjectDir "DynamicLightingDriver.csproj"
$PackageDir = Join-Path $ProjectDir "Package"
$ManifestPath = Join-Path $PackageDir "AppxManifest.xml"

# Determine build output directory
$Tfm = "net9.0-windows10.0.26100.0"
$OutputDir = Join-Path $ProjectDir "bin\$Configuration\$Tfm"

# Find Windows SDK tools
$SdkBinDir = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory |
    Where-Object { $_.Name -match '^\d' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
$MakeAppx = Join-Path $SdkBinDir.FullName "x64\MakeAppx.exe"
$SignTool = Join-Path $SdkBinDir.FullName "x64\SignTool.exe"

Write-Host "=== Dynamic Lighting Driver — Ambient App Registration ===" -ForegroundColor Cyan

# Step 1: Build
Write-Host "`nStep 1: Building project..." -ForegroundColor Yellow
dotnet build $CsprojPath -c $Configuration
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}
Write-Host "  Build succeeded." -ForegroundColor Green

# Step 2: Create or find self-signed certificate
Write-Host "`nStep 2: Ensuring signing certificate exists..." -ForegroundColor Yellow
$Publisher = "CN=DynamicLightingDriver"
$cert = Get-ChildItem "Cert:\CurrentUser\My" | Where-Object { $_.Subject -eq $Publisher -and $_.NotAfter -gt (Get-Date) } | Select-Object -First 1

if (-not $cert) {
    Write-Host "  Creating self-signed certificate..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate `
        -Type Custom `
        -Subject $Publisher `
        -KeyUsage DigitalSignature `
        -FriendlyName "Dynamic Lighting Driver Dev Certificate" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Write-Host "  Created certificate: $($cert.Thumbprint)" -ForegroundColor Green
} else {
    Write-Host "  Found existing certificate: $($cert.Thumbprint)" -ForegroundColor Green
}

# Import to Trusted People stores
$certFile = Join-Path $env:TEMP "DynamicLightingDriver.cer"
Export-Certificate -Cert $cert -FilePath $certFile | Out-Null

$existingUser = Get-ChildItem "Cert:\CurrentUser\TrustedPeople" -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
if (-not $existingUser) {
    Import-Certificate -FilePath $certFile -CertStoreLocation "Cert:\CurrentUser\TrustedPeople" | Out-Null
    Write-Host "  Imported to CurrentUser\TrustedPeople" -ForegroundColor Green
}

$existingMachine = Get-ChildItem "Cert:\LocalMachine\TrustedPeople" -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
if (-not $existingMachine) {
    Write-Host "  Importing to LocalMachine\TrustedPeople (may require elevation)..." -ForegroundColor Yellow
    Import-Certificate -FilePath $certFile -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" | Out-Null
    Write-Host "  Imported to LocalMachine\TrustedPeople" -ForegroundColor Green
}

Remove-Item $certFile -ErrorAction SilentlyContinue

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

# Also remove old DynamicLightingMcp package if present
$oldPkg = Get-AppxPackage -Name "DynamicLightingMcp" -ErrorAction SilentlyContinue
if ($oldPkg) {
    Write-Host "  Removing old DynamicLightingMcp package..." -ForegroundColor Yellow
    Remove-AppxPackage $oldPkg.PackageFullName
    Start-Sleep -Seconds 2
    Write-Host "  Removed old package." -ForegroundColor Green
}

# Step 4: Create staging directory and .msix
Write-Host "`nStep 4: Creating signed .msix package..." -ForegroundColor Yellow
$StageDir = Join-Path $ProjectDir "PackageStaging"
$MsixPath = Join-Path $ProjectDir "DynamicLightingDriver.msix"

if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item $StageDir -ItemType Directory | Out-Null

# Copy manifest, assets, public folder, and exe
Copy-Item $ManifestPath "$StageDir\AppxManifest.xml" -Force
Copy-Item (Join-Path $PackageDir "Assets") "$StageDir\Assets" -Recurse
if (Test-Path (Join-Path $PackageDir "public")) {
    Copy-Item (Join-Path $PackageDir "public") "$StageDir\public" -Recurse
}
Copy-Item (Join-Path $OutputDir "DynamicLightingDriver.exe") "$StageDir\" -Force

# Create .msix
Remove-Item $MsixPath -ErrorAction SilentlyContinue
& $MakeAppx pack /d $StageDir /p $MsixPath /o | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "MakeAppx failed."
    exit 1
}
Write-Host "  Created .msix" -ForegroundColor Green

# Sign .msix
& $SignTool sign /fd SHA256 /sha1 $cert.Thumbprint /td SHA256 $MsixPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "SignTool failed."
    exit 1
}
Write-Host "  Signed .msix" -ForegroundColor Green

# Clean up staging
Remove-Item $StageDir -Recurse -Force

# Step 5: Install signed package with external location
Write-Host "`nStep 5: Installing signed package..." -ForegroundColor Yellow
Write-Host "  .msix: $MsixPath"
Write-Host "  External location: $OutputDir"

Add-AppxPackage -Path $MsixPath -ExternalLocation $OutputDir

Write-Host "  Installation succeeded!" -ForegroundColor Green

# Step 6: Verify
Write-Host "`nStep 6: Verifying registration..." -ForegroundColor Yellow
$pkg = Get-AppxPackage -Name "DynamicLightingDriver"
if ($pkg) {
    Write-Host "  Package: $($pkg.PackageFullName)" -ForegroundColor Green
    Write-Host "  Status:  $($pkg.Status)" -ForegroundColor Green
    Write-Host "  SignatureKind: $($pkg.SignatureKind)" -ForegroundColor Green
} else {
    Write-Warning "  Package not found after installation. Check for errors above."
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host 'Your app should now appear in:'
Write-Host '  Settings -> Personalization -> Dynamic Lighting -> Background light control'
Write-Host ''
Write-Host 'To unregister: Get-AppxPackage *DynamicLightingDriver* | Remove-AppxPackage'
