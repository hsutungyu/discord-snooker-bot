#Requires -Version 5.1
<#
.SYNOPSIS
    Builds the Discord snooker bot Docker image and pushes it to the
    Gitea container registry at git.19371928.xyz.

.PARAMETER Tag
    Image tag to apply. Defaults to 'latest'.

.EXAMPLE
    .\build-and-push.ps1
    .\build-and-push.ps1 -Tag 1.2.3
#>

param(
    [string]$Tag = "latest"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Registry = "git.19371928.xyz"
$ImagePath = "automation/discord-snooker"
$FullImage = "${Registry}/${ImagePath}:${Tag}"

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

# Also tag as latest if a specific version was provided
if ($Tag -ne "latest") {
    $LatestImage = "${Registry}/${ImagePath}:latest"
    Write-Host "==> Tagging as $LatestImage ..." -ForegroundColor Cyan
    docker tag $FullImage $LatestImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker tag failed."
    }
}

# Push versioned tag
Write-Host "==> Pushing $FullImage ..." -ForegroundColor Cyan
docker push $FullImage
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker push failed."
}

# Push latest tag if a version was provided
if ($Tag -ne "latest") {
    Write-Host "==> Pushing $LatestImage ..." -ForegroundColor Cyan
    docker push $LatestImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker push (latest) failed."
    }
}

Write-Host "==> Done. Image pushed: $FullImage" -ForegroundColor Green
