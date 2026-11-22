# Registers (or removes) the Windows Scheduled Task that runs `claude-lens scan`
# once a day, pushing new Claude Code transcript lines to the Claude Lens
# Postgres database. Also removes the old Token Dashboard task it replaces.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1              # daily at 13:00
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -At 09:30
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -Uninstall
#
# The task runs as the current user, only while logged on (no password stored),
# with the backend venv's pythonw.exe so no console window flashes. Its working
# directory is the repo root, where `.env.local` (DATABASE_URL) is found. If the
# PC is off or asleep at the scheduled time, it runs as soon as possible after.
# Output goes to %USERPROFILE%\.claude\claude-lens-sync.log (1 MB, 1 backup).

param(
    [string]$At = "13:00",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "Claude Lens - Daily Sync"
$OldTaskName = "Claude Token Dashboard - Daily Scan"

function Remove-TaskIfPresent([string]$Name) {
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Host "Removed scheduled task '$Name'."
    }
}

if ($Uninstall) {
    Remove-TaskIfPresent $TaskName
    return
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $RepoRoot "backend\.venv"
$Pythonw = Join-Path $Venv "Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    throw "backend\.venv not found ($Pythonw). Run ``uv sync`` in backend first."
}
if (-not (Test-Path (Join-Path $RepoRoot ".env.local"))) {
    Write-Warning "No .env.local at $RepoRoot - the task will fail until DATABASE_URL is set there."
}

Remove-TaskIfPresent $OldTaskName

$Arguments = "-m claude_lens.cli scan"
$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument $Arguments -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal `
    -Description "Claude Lens: pushes new ~/.claude/projects transcript lines to Postgres (claude-lens scan)." `
    -Force | Out-Null

Write-Host "Registered '$TaskName' - daily at $At."
Write-Host "  runs: $Pythonw $Arguments"
Write-Host "  in:   $RepoRoot"
Write-Host "  log:  $env:USERPROFILE\.claude\claude-lens-sync.log"
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"
