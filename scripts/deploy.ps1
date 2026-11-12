<#
  Deploy site/ to cukivan.me/meniny over FTPS (same WebHouse account as the sibling sites).

  Server and user are not hardcoded because this repository is meant to be public;
  pass them or set DEPLOY_FTP_SERVER / DEPLOY_FTP_USER (same values as varim/scripts/deploy.ps1).
  The password is the Bitwarden secret MAJSTER_FTP_PASSWORD, injected by
  whispair-ops/scripts/invoke-with-bitwarden.ps1; -Prompt asks for it instead.

  Only uploads, never deletes: site/api/store/votes.json and salt.txt live only on the
  server and are not part of the payload, so a deploy cannot wipe the votes.

    pwsh -NoProfile -File D:\cukivan.me\meniny\scripts\deploy.ps1 -Go   # upload
    pwsh -NoProfile -File D:\cukivan.me\meniny\scripts\deploy.ps1       # dry run only
#>
[CmdletBinding()]
param(
  [string]$Server = $env:DEPLOY_FTP_SERVER,
  [string]$User = $env:DEPLOY_FTP_USER,
  # A subpage of the main site rather than a subdomain: it reuses the existing HTTPS
  # certificate, so nothing has to be set up in the WebHouse panel first.
  [string]$Root = '/www_root_cukivan_me/meniny',
  [string]$CheckUrl = 'https://cukivan.me/meniny/',
  [switch]$Prompt,
  [switch]$Go
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Server -or -not $User) { throw 'Set -Server and -User (or DEPLOY_FTP_SERVER / DEPLOY_FTP_USER).' }

if (-not $env:MAJSTER_FTP_PASSWORD -and -not $Prompt -and -not $env:MENINY_BITWARDEN_TRIED) {
  # Re-run this script with the secret injected. whispair-ops sits on the same drive.
  $bitwarden = 'D:\whispAir-IT\whispair-ops\scripts\invoke-with-bitwarden.ps1'
  if (Test-Path -LiteralPath $bitwarden) {
    $env:MENINY_BITWARDEN_TRIED = '1'
    $arguments = @('-NoProfile', '-File', $PSCommandPath, '-Server', $Server, '-User', $User)
    if ($Go) { $arguments += '-Go' }
    & $bitwarden -Environment development -Command 'pwsh' -Arguments $arguments
    exit $LASTEXITCODE
  }
}

if ($env:MAJSTER_FTP_PASSWORD) {
  $env:DEPLOY_FTP_PASSWORD = $env:MAJSTER_FTP_PASSWORD
} else {
  $secure = Read-Host "FTP password for $User@$Server" -AsSecureString
  $env:DEPLOY_FTP_PASSWORD = [Net.NetworkCredential]::new('', $secure).Password
}
try {
  [string[]]$mode = @()
  if (-not $Go) { $mode = @('--dry-run') }
  $watch = [Diagnostics.Stopwatch]::StartNew()
  & python -I (Join-Path $PSScriptRoot 'ftps_upload.py') $Server $User $Root (Join-Path $repo 'site') @mode
  if ($LASTEXITCODE -ne 0) { throw "upload failed (exit $LASTEXITCODE)" }
  Write-Host ("Done in {0:n1} s ({1})." -f $watch.Elapsed.TotalSeconds, $(if ($Go) { 'uploaded' } else { 'dry run, add -Go' }))
  if ($Go) {
    try {
      $page = (Invoke-WebRequest -Uri $CheckUrl -UseBasicParsing -Headers @{ 'Cache-Control' = 'no-cache' }).Content
      if ($page -match 'Meniny pod') { Write-Host "OK: $CheckUrl serves the site." }
      else { Write-Warning "$CheckUrl does not serve the site yet." }
    } catch {
      Write-Warning "$CheckUrl cannot be opened: $($_.Exception.Message) "
    }
  }
} finally {
  Remove-Item Env:DEPLOY_FTP_PASSWORD -ErrorAction SilentlyContinue
}
