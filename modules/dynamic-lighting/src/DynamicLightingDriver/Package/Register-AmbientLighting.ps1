<#
.SYNOPSIS
    Registers the Dynamic Lighting Driver as an ambient lighting app using WinAppCLI.
.DESCRIPTION
    This script:
    1. Builds the .NET project
    2. Stages the package layout (manifest, assets, public folder, exe)
    3. Uses 'winapp package' to create and sign an MSIX with an auto-generated dev certificate
    4. Installs the signed package with external content pointing to build output
    After registration, the app appears in Settings > Personalization > Dynamic Lighting > Background light control
    and can control lighting in the background without needing foreground focus.
.NOTES
    Requires WinAppCLI (winget install Microsoft.WinAppCli).
    Requires elevation (admin) for certificate trust via --install-cert.
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
$OutputDir = Join-Path $ProjectDir "bin\$Configuration\$Tfm"

Write-Host "=== Dynamic Lighting Driver — Ambient App Registration ===" -ForegroundColor Cyan

# Step 1: Build
Write-Host "`nStep 1: Building project..." -ForegroundColor Yellow
dotnet build $CsprojPath -c $Configuration
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}
Write-Host "  Build succeeded." -ForegroundColor Green

# Step 2: Unregister previous version if present
Write-Host "`nStep 2: Checking for existing registration..." -ForegroundColor Yellow
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

# Step 3: Stage package layout
Write-Host "`nStep 3: Staging package layout..." -ForegroundColor Yellow
$StageDir = Join-Path $ProjectDir "PackageStaging"
$MsixPath = Join-Path $ProjectDir "DynamicLightingDriver.msix"

if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item $StageDir -ItemType Directory | Out-Null

# Copy manifest and patch ProcessorArchitecture to match runtime
$ManifestContent = Get-Content $ManifestPath -Raw
$Arch = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq [System.Runtime.InteropServices.Architecture]::Arm64) { "arm64" } else { "x64" }
$ManifestContent = $ManifestContent -replace 'ProcessorArchitecture="[^"]*"', "ProcessorArchitecture=`"$Arch`""
Set-Content "$StageDir\AppxManifest.xml" $ManifestContent -Encoding UTF8
Write-Host "  Patched manifest ProcessorArchitecture to $Arch" -ForegroundColor Green

Copy-Item (Join-Path $PackageDir "Assets") "$StageDir\Assets" -Recurse
if (Test-Path (Join-Path $PackageDir "public")) {
    Copy-Item (Join-Path $PackageDir "public") "$StageDir\public" -Recurse
}
Copy-Item (Join-Path $OutputDir "DynamicLightingDriver.exe") "$StageDir\" -Force
Write-Host "  Layout staged at: $StageDir" -ForegroundColor Green

# Step 4: Ensure signing certificate exists
Write-Host "`nStep 4: Ensuring signing certificate..." -ForegroundColor Yellow
$Publisher = "CN=DynamicLightingDriver"
$CertDir = Join-Path $ProjectDir "Package"
$CertPath = Join-Path $CertDir "devcert.pfx"
$NeedsTrust = $false

if (-not (Test-Path $CertPath)) {
    Write-Host "  No PFX found, generating with WinAppCLI..." -ForegroundColor Yellow
    winapp cert generate --publisher $Publisher --output $CertPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "winapp cert generate failed."
        exit 1
    }
    $NeedsTrust = $true
    Write-Host "  Generated dev certificate" -ForegroundColor Green
} else {
    Write-Host "  Using existing certificate: $CertPath" -ForegroundColor Green
}

# Trust the cert if newly generated
if ($NeedsTrust) {
    Write-Host "  Installing certificate to trusted stores..." -ForegroundColor Yellow
    winapp cert install $CertPath 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  winapp cert install needs admin, falling back to Import-Certificate..." -ForegroundColor Yellow
        $pfxPass = ConvertTo-SecureString "password" -AsPlainText -Force
        $cert = Import-PfxCertificate -FilePath $CertPath -CertStoreLocation "Cert:\CurrentUser\My" -Password $pfxPass
        $certFile = Join-Path $env:TEMP "DynamicLightingDriver.cer"
        Export-Certificate -Cert $cert -FilePath $certFile | Out-Null
        Import-Certificate -FilePath $certFile -CertStoreLocation "Cert:\CurrentUser\TrustedPeople" | Out-Null
        try {
            Import-Certificate -FilePath $certFile -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" | Out-Null
            Write-Host "  Imported to LocalMachine\TrustedPeople" -ForegroundColor Green
        } catch {
            Write-Warning "  Could not import to LocalMachine\TrustedPeople (need admin). Run once as admin to trust."
        }
        Remove-Item $certFile -ErrorAction SilentlyContinue
    }
}
Write-Host "  Certificate ready" -ForegroundColor Green

# Step 5: Create signed .msix using WinAppCLI
Write-Host "`nStep 5: Creating signed .msix with WinAppCLI..." -ForegroundColor Yellow
Remove-Item $MsixPath -ErrorAction SilentlyContinue

winapp package $StageDir `
    --manifest "$StageDir\AppxManifest.xml" `
    --output $MsixPath `
    --cert $CertPath `
    --publisher "CN=DynamicLightingDriver"

if ($LASTEXITCODE -ne 0) {
    Write-Error "winapp package failed."
    exit 1
}
Write-Host "  Created and signed .msix" -ForegroundColor Green

# Clean up staging
Remove-Item $StageDir -Recurse -Force

# Step 6: Install signed package with external location
Write-Host "`nStep 6: Installing signed package..." -ForegroundColor Yellow
Write-Host "  .msix: $MsixPath"
Write-Host "  External location: $OutputDir"

Add-AppxPackage -Path $MsixPath -ExternalLocation $OutputDir

Write-Host "  Installation succeeded!" -ForegroundColor Green

# Step 7: Verify
Write-Host "`nStep 7: Verifying registration..." -ForegroundColor Yellow
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
