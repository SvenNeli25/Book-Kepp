param(
  [switch]$Installer
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$outRoot = Join-Path $env:USERPROFILE ".codex\\memories\\Book-Keep\\build-out"
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$workPath = Join-Path $outRoot "work"
$distPath = Join-Path $outRoot "dist"

Write-Host "Building Book-Keep (PyInstaller) into $distPath ..."
python -m PyInstaller --noconfirm --clean --workpath $workPath --distpath $distPath (Join-Path $repoRoot "build\\pyinstaller.spec")

if ($Installer) {
  Write-Host "Building installer (Inno Setup)..."
  $isccCmd = (Get-Command iscc -ErrorAction SilentlyContinue)
  if (-not $isccCmd) {
    $candidates = @(
      "${env:ProgramFiles}\\Inno Setup 6\\ISCC.exe",
      "${env:ProgramFiles}\\Inno Setup 5\\ISCC.exe",
      "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe",
      "${env:ProgramFiles}\\Inno Setup 6\\ISCC.exe",
      "${env:ProgramFiles}\\Inno Setup 5\\ISCC.exe"
    )

    # PowerShell needs ${env:ProgramFiles(x86)} for this var name.
    $pf86 = ${env:ProgramFiles(x86)}
    if ($pf86) {
      $candidates += @(
        (Join-Path $pf86 "Inno Setup 6\\ISCC.exe"),
        (Join-Path $pf86 "Inno Setup 5\\ISCC.exe")
      )
    }

    $candidates = $candidates | Where-Object { $_ -and (Test-Path $_) }

    if ($candidates.Count -gt 0) {
      $isccCmd = $candidates[0]
      Write-Host "Found ISCC at: $isccCmd"
    } else {
      throw "Inno Setup is not installed or ISCC.exe is not on PATH. Install Inno Setup, or add ISCC.exe to PATH."
    }
  } else {
    $isccCmd = $isccCmd.Source
  }

  $versionFile = Join-Path $repoRoot "app_version.py"
  $pattern = '^__version__\s*=\s*"([^"]+)"\s*$'
  $verLine = (Get-Content -Path $versionFile | Where-Object { $_ -match $pattern } | Select-Object -First 1)
  if (-not $verLine) { throw "Could not read __version__ from app_version.py" }
  $ver = [regex]::Match($verLine, $pattern).Groups[1].Value
  if (-not $ver) { throw "Invalid __version__ in app_version.py" }

  $srcDir = Join-Path $distPath "Book-Keep"
  if (-not (Test-Path $srcDir)) { throw "PyInstaller output not found: $srcDir" }

  & $isccCmd ("/DAppVersion=$ver") ("/DSourceDir=$srcDir") (Join-Path $repoRoot "build\\installer.iss")
}

Write-Host "Done."
