Param(
  # Repo root containing ".claude\skills\sol". Defaults to the parent of this script's folder.
  [Parameter(Mandatory = $false)]
  [string]$RepoRoot,

  # Destination root for user-level Claude skills.
  [Parameter(Mandatory = $false)]
  [string]$UserClaudeDir = (Join-Path $env:USERPROFILE ".claude"),

  # Where backups go. Deliberately OUTSIDE the skills root: a copy left inside it is
  # loaded by Claude Code as a second, stale skill with the same description.
  [Parameter(Mandatory = $false)]
  [string]$BackupRoot,

  # Overwrite existing installed skill.
  [Parameter(Mandatory = $false)]
  [switch]$Force,

  # Keep a timestamped copy of the installed skill under $BackupRoot before overwriting.
  [Parameter(Mandatory = $false)]
  [switch]$Backup
)

$ErrorActionPreference = "Stop"

function Assert-DirExists([string]$Path, [string]$What) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    throw "$What non trovato: $Path"
  }
}

# $PSScriptRoot can be empty inside a param() default when the script is invoked with a
# relative path via -File on Windows PowerShell 5.1, so resolve the default here instead.
if (-not $RepoRoot) {
  $scriptDir = $PSScriptRoot
  if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
  if (-not $scriptDir) {
    throw "Impossibile dedurre RepoRoot: passalo esplicitamente con -RepoRoot <path-del-repo>."
  }
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

if (-not $BackupRoot) {
  $BackupRoot = Join-Path $UserClaudeDir "skills-backup"
}

$sourceSkillDir = Join-Path $RepoRoot ".claude\skills\sol"
$destSkillsRoot = Join-Path $UserClaudeDir "skills"
$destSkillDir = Join-Path $destSkillsRoot "sol"

Assert-DirExists $RepoRoot "RepoRoot"
Assert-DirExists $sourceSkillDir "Directory skill sorgente"

# Guard against a BackupRoot that sits inside the skills tree, which would defeat the point.
$sep = [System.IO.Path]::DirectorySeparatorChar
$normalizedBackupRoot = [System.IO.Path]::GetFullPath($BackupRoot).TrimEnd($sep)
$normalizedSkillsRoot = [System.IO.Path]::GetFullPath($destSkillsRoot).TrimEnd($sep)
if ($normalizedBackupRoot -eq $normalizedSkillsRoot -or
    $normalizedBackupRoot.StartsWith($normalizedSkillsRoot + $sep,
                                     [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "BackupRoot non puo' stare dentro la cartella delle skill ($destSkillsRoot): la copia verrebbe caricata come una seconda skill. Scegli un percorso fuori da li'."
}

if (-not (Test-Path -LiteralPath $destSkillsRoot -PathType Container)) {
  New-Item -ItemType Directory -Path $destSkillsRoot -Force | Out-Null
}

$backupDir = $null

if (Test-Path -LiteralPath $destSkillDir) {
  if (-not $Force) {
    throw "La skill risulta gia' installata in: $destSkillDir. Usa -Force per sovrascrivere (opzionale: -Backup)."
  }

  if ($Backup) {
    if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) {
      New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    }
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $BackupRoot ("sol-$timestamp")
    if (Test-Path -LiteralPath $backupDir) {
      throw "Backup dir gia' esistente (inaspettato): $backupDir"
    }
    Move-Item -LiteralPath $destSkillDir -Destination $backupDir
  } else {
    Remove-Item -LiteralPath $destSkillDir -Recurse -Force
  }
}

# Copia l'intera directory "sol" per evitare edge-case su Windows con Copy-Item "$dir\*".
Copy-Item -LiteralPath $sourceSkillDir -Destination $destSkillsRoot -Recurse -Force

$skillFile = Join-Path $destSkillDir "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
  throw "Install completata ma manca SKILL.md in: $skillFile"
}

Write-Host "OK: skill 'sol' installata in $destSkillDir"
if ($backupDir) {
  Write-Host "Copia precedente salvata in $backupDir (fuori dalla cartella delle skill)."
}
Write-Host "Suggerimento: riavvia Claude Code/Cursor se non la vede subito."
