Param(
  # Repo root containing ".claude\skills\sol". Defaults to parent of this script's folder.
  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,

  # Destination root for user-level Claude skills.
  [Parameter(Mandatory = $false)]
  [string]$UserClaudeDir = (Join-Path $env:USERPROFILE ".claude"),

  # Overwrite existing installed skill.
  [Parameter(Mandatory = $false)]
  [switch]$Force,

  # Backup existing installed skill to "sol.backup-<timestamp>" before overwrite.
  [Parameter(Mandatory = $false)]
  [switch]$Backup
)

$ErrorActionPreference = "Stop"

function Assert-DirExists([string]$Path, [string]$What) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    throw "$What non trovato: $Path"
  }
}

$sourceSkillDir = Join-Path $RepoRoot ".claude\skills\sol"
$destSkillsRoot = Join-Path $UserClaudeDir "skills"
$destSkillDir = Join-Path $destSkillsRoot "sol"

Assert-DirExists $RepoRoot "RepoRoot"
Assert-DirExists $sourceSkillDir "Directory skill sorgente"

if (-not (Test-Path -LiteralPath $destSkillsRoot -PathType Container)) {
  New-Item -ItemType Directory -Path $destSkillsRoot -Force | Out-Null
}

if (Test-Path -LiteralPath $destSkillDir) {
  if (-not $Force) {
    throw "La skill risulta già installata in: $destSkillDir. Usa -Force per sovrascrivere (opzionale: -Backup)."
  }

  if ($Backup) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $destSkillsRoot ("sol.backup-$timestamp")
    if (Test-Path -LiteralPath $backupDir) {
      throw "Backup dir già esistente (inaspettato): $backupDir"
    }
    Rename-Item -LiteralPath $destSkillDir -NewName ("sol.backup-$timestamp")
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
Write-Host "Suggerimento: riavvia Claude Code/Cursor se non la vede subito."
