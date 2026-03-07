#Requires -Version 5.1
<#
.SYNOPSIS
    Builds the Discord snooker bot Docker image and pushes it to the
    Gitea container registry at git.19371928.xyz.
    After a successful push the image tag in deploy.yaml is updated.

.PARAMETER Tag
    Image tag to apply. Defaults to a UTC timestamp (yyyyMMdd-HHmmss).

.EXAMPLE
    .\build-and-push.ps1
    .\build-and-push.ps1 -Tag 1.2.3
#>

param(
    [string]$Tag = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Registry  = "git.19371928.xyz"
$ImagePath = "automation/discord-snooker"
$FullImage = "${Registry}/${ImagePath}:${Tag}"
$DeployFile = Join-Path $PSScriptRoot "deploy.yaml"

Write-Host "==> Image : $FullImage" -ForegroundColor Cyan

# Ensure docker is available
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not in PATH."
}

# Log in to the Gitea registry (no-op if already authenticated)
Write-Host "==> Logging in to $Registry ..." -ForegroundColor Cyan
docker login $Registry
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker login failed."
}

# Build
Write-Host "==> Building $FullImage ..." -ForegroundColor Cyan
docker build -t $FullImage .
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker build failed."
}

# Push
Write-Host "==> Pushing $FullImage ..." -ForegroundColor Cyan
docker push $FullImage
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker push failed."
}

# Update the image tag in deploy.yaml
Write-Host "==> Updating image tag in deploy.yaml ..." -ForegroundColor Cyan
$content = Get-Content $DeployFile -Raw
$updated = $content -replace "${Registry}/${ImagePath}:[^\s`"']+", "${FullImage}"
Set-Content -Path $DeployFile -Value $updated.TrimEnd()
Write-Host "==> deploy.yaml updated to $FullImage" -ForegroundColor Green

Write-Host "==> Done. Image pushed: $FullImage" -ForegroundColor Green
