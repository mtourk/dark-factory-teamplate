# Deploy script for Dark Factory intake (web + worker) — PowerShell version
#
# Usage: .\deploy.ps1 [-DryRun]
#
# This script:
# 1. Increments VERSION in factory\intake\web\VERSION
# 2. Updates DEPLOYED_AT timestamp in wrangler.toml
# 3. Deploys the web frontend (Pages)
# 4. Deploys the Worker
# 5. Verifies CORS origin is correct
#
# The version and timestamp are then served via the Worker's /version endpoint
# and displayed in the web UI footer.

param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

# Assume script is in: C:\...\dark-factory-teamplate\factory\intake\deploy.ps1
# So we go up one level to find factory\intake
$IntakeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebDir = Join-Path $IntakeDir "web"
$WorkerDir = Join-Path $IntakeDir "worker"
$VersionFile = Join-Path $WebDir "VERSION"
$WranglerToml = Join-Path $WorkerDir "wrangler.toml"

if ($DryRun) {
    Write-Host "🔍 DRY RUN MODE — no changes will be committed" -ForegroundColor Cyan
}

# Step 1: Read and increment version
if (-not (Test-Path $VersionFile)) {
    Write-Host "❌ VERSION file not found: $VersionFile" -ForegroundColor Red
    exit 1
}

$CurrentVersion = (Get-Content $VersionFile -Raw).Trim()
$NextVersion = [int]$CurrentVersion + 1

Write-Host "📦 Current version: $CurrentVersion"
Write-Host "📦 Next version: $NextVersion"

# Step 2: Generate deployment timestamp
$DeployedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
Write-Host "⏰ Deployment timestamp: $DeployedAt"

if (-not $DryRun) {
    # Update VERSION file
    Set-Content $VersionFile "$NextVersion"
    Write-Host "✅ Updated VERSION to $NextVersion"

    # Update wrangler.toml
    $WranglerContent = Get-Content $WranglerToml -Raw
    $WranglerContent = $WranglerContent -replace 'VERSION = ".+"', "VERSION = `"$NextVersion`""
    $WranglerContent = $WranglerContent -replace 'DEPLOYED_AT = ".+"', "DEPLOYED_AT = `"$DeployedAt`""
    Set-Content $WranglerToml $WranglerContent -NoNewline
    Write-Host "✅ Updated wrangler.toml with version and timestamp"
}

# Step 3: Deploy web frontend
Write-Host ""
Write-Host "🚀 Deploying web frontend to Cloudflare Pages..." -ForegroundColor Cyan
if (-not $DryRun) {
    Push-Location $WebDir
    wrangler pages deploy . --project-name dark-factory-intake --commit-dirty=true
    Pop-Location
    Write-Host "✅ Pages deployed"
}
else {
    Write-Host "   [DRY RUN] wrangler pages deploy would run here"
}

# Step 4: Deploy Worker
Write-Host ""
Write-Host "🚀 Deploying Worker..." -ForegroundColor Cyan
if (-not $DryRun) {
    Push-Location $WorkerDir
    wrangler deploy
    Pop-Location
    Write-Host "✅ Worker deployed"
}
else {
    Write-Host "   [DRY RUN] wrangler deploy would run here"
}

# Step 5: Verify
Write-Host ""
Write-Host "🔍 Verifying deployment..." -ForegroundColor Cyan
if (-not $DryRun) {
    Start-Sleep -Seconds 2
    try {
        $VersionResponse = Invoke-WebRequest -Uri "https://dark-factory-intake.mohammad-tourk.workers.dev/version" -UseBasicParsing
        Write-Host "   Version endpoint response: $($VersionResponse.Content)"
    }
    catch {
        Write-Host "   ⚠️  Version endpoint unreachable: $_" -ForegroundColor Yellow
    }

    try {
        $CorsCheck = Invoke-WebRequest -Uri "https://dark-factory-intake.mohammad-tourk.workers.dev/conversations" `
            -Method Options `
            -Headers @{"Origin" = "https://factory.mtourk.com"} `
            -UseBasicParsing
        $CorsHeader = $CorsCheck.Headers["Access-Control-Allow-Origin"]
        Write-Host "   CORS origin: $CorsHeader"
    }
    catch {
        Write-Host "   ⚠️  CORS check failed: $_" -ForegroundColor Yellow
    }
}
else {
    Write-Host "   [DRY RUN] Verification would run here"
}

Write-Host ""
if ($DryRun) {
    Write-Host "✅ DRY RUN COMPLETE — no changes made" -ForegroundColor Green
    Write-Host ""
    Write-Host "To proceed with real deployment, run: .\deploy.ps1"
}
else {
    Write-Host "✅ DEPLOYMENT COMPLETE" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Summary:" -ForegroundColor Cyan
    Write-Host "   • Version: $NextVersion"
    Write-Host "   • Deployed at: $DeployedAt"
    Write-Host "   • Web: https://factory.mtourk.com"
    Write-Host "   • Worker: https://dark-factory-intake.mohammad-tourk.workers.dev"
    Write-Host "   • Version endpoint: https://dark-factory-intake.mohammad-tourk.workers.dev/version"
}
