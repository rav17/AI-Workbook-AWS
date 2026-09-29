# ==============================================================================
# MFA Authentication Helper for AWS CLI
# ==============================================================================
# Usage:
#   .\scripts\mfa_auth.ps1 -TokenCode 123456
#
# Writes MFA temp credentials to ~/.aws/credentials as [mfa] profile.
# Works across all terminals after running.
# ==============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$TokenCode,

    [Parameter(Mandatory=$false)]
    [int]$Duration = 43200,

    [Parameter(Mandatory=$false)]
    [string]$MfaSerial = "arn:aws:iam::533267042240:mfa/Ravindra",

    [Parameter(Mandatory=$false)]
    [string]$SourceProfile = "default",

    [Parameter(Mandatory=$false)]
    [string]$TargetProfile = "mfa"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== AWS MFA Authentication ===" -ForegroundColor Cyan
Write-Host "MFA Device:      $MfaSerial"
Write-Host "Duration:        $Duration seconds"
Write-Host "Source Profile:  $SourceProfile"
Write-Host "Target Profile:  $TargetProfile"
Write-Host ""

if ($TokenCode -notmatch '^\d{6}$') {
    Write-Host "ERROR: MFA code must be exactly 6 digits." -ForegroundColor Red
    exit 1
}

# Clear env vars so base creds from source profile are used
$env:AWS_SESSION_TOKEN = $null
$env:AWS_ACCESS_KEY_ID = $null
$env:AWS_SECRET_ACCESS_KEY = $null
$env:AWS_PROFILE = $null

Write-Host "Requesting temporary credentials from STS..." -ForegroundColor Yellow

# Call STS using Start-Process to capture output cleanly
$tempFile = [System.IO.Path]::GetTempFileName()
$errFile = [System.IO.Path]::GetTempFileName()

$proc = Start-Process -FilePath "aws" -ArgumentList "sts","get-session-token","--serial-number",$MfaSerial,"--token-code",$TokenCode,"--duration-seconds",$Duration,"--profile",$SourceProfile,"--output","json" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tempFile -RedirectStandardError $errFile

if ($proc.ExitCode -ne 0) {
    $errMsg = Get-Content $errFile -Raw
    Write-Host "ERROR: STS call failed." -ForegroundColor Red
    Write-Host $errMsg -ForegroundColor Red
    Remove-Item $tempFile -Force
    Remove-Item $errFile -Force
    exit 1
}

$jsonOutput = Get-Content $tempFile -Raw
Remove-Item $tempFile -Force
Remove-Item $errFile -Force

$creds = $jsonOutput | ConvertFrom-Json
$accessKey = $creds.Credentials.AccessKeyId
$secretKey = $creds.Credentials.SecretAccessKey
$sessionToken = $creds.Credentials.SessionToken
$expiration = $creds.Credentials.Expiration

Write-Host "Got temporary credentials (expires: $expiration)" -ForegroundColor Green

# Write to ~/.aws/credentials file
$awsDir = Join-Path $env:USERPROFILE ".aws"
$credFile = Join-Path $awsDir "credentials"

if (-not (Test-Path $credFile)) {
    Write-Host "ERROR: $credFile not found" -ForegroundColor Red
    exit 1
}

# Read existing file lines
$lines = [System.IO.File]::ReadAllLines($credFile)

# Remove existing [mfa] section
$newLines = @()
$skipping = $false
foreach ($line in $lines) {
    if ($line -match "^\[$([regex]::Escape($TargetProfile))\]") {
        $skipping = $true
        continue
    }
    if ($skipping -and $line -match "^\[") {
        $skipping = $false
    }
    if (-not $skipping) {
        $newLines += $line
    }
}

# Remove trailing empty lines
while ($newLines.Count -gt 0 -and $newLines[-1].Trim() -eq "") {
    $newLines = $newLines[0..($newLines.Count - 2)]
}

# Append new [mfa] profile
$newLines += ""
$newLines += "[$TargetProfile]"
$newLines += "aws_access_key_id = $accessKey"
$newLines += "aws_secret_access_key = $secretKey"
$newLines += "aws_session_token = $sessionToken"

[System.IO.File]::WriteAllLines($credFile, $newLines)
Write-Host "Wrote [$TargetProfile] profile to $credFile" -ForegroundColor Green

# Ensure config file has the profile region
$configFile = Join-Path $awsDir "config"
if (Test-Path $configFile) {
    $configText = [System.IO.File]::ReadAllText($configFile)
    if ($configText -notmatch "\[profile $TargetProfile\]") {
        $addition = "`n[profile $TargetProfile]`nregion = us-east-1`noutput = json`n"
        [System.IO.File]::AppendAllText($configFile, $addition)
        Write-Host "Added [profile $TargetProfile] to config" -ForegroundColor DarkGray
    }
}

# Set profile for current session
$env:AWS_PROFILE = $TargetProfile

# Verify
Write-Host "Verifying..." -ForegroundColor Yellow
$verifyFile = [System.IO.Path]::GetTempFileName()
$verifyErr = [System.IO.Path]::GetTempFileName()
$vProc = Start-Process -FilePath "aws" -ArgumentList "sts","get-caller-identity","--profile",$TargetProfile,"--output","json" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $verifyFile -RedirectStandardError $verifyErr

if ($vProc.ExitCode -ne 0) {
    $vErr = Get-Content $verifyErr -Raw
    Write-Host "WARNING: Verification failed - $vErr" -ForegroundColor Yellow
} else {
    $idJson = Get-Content $verifyFile -Raw
    $id = $idJson | ConvertFrom-Json
    Write-Host ""
    Write-Host "=== SUCCESS ===" -ForegroundColor Green
    Write-Host "  Account:  $($id.Account)"
    Write-Host "  User:     $($id.Arn)"
    Write-Host "  Expires:  $expiration"
    Write-Host "  Profile:  $TargetProfile"
    Write-Host ""
    Write-Host "Now use:  --profile mfa   (or set `$env:AWS_PROFILE = 'mfa'`)" -ForegroundColor Cyan
    Write-Host ""
}

Remove-Item $verifyFile -Force -ErrorAction SilentlyContinue
Remove-Item $verifyErr -Force -ErrorAction SilentlyContinue
