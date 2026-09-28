# Registers (or removes) a Windows Scheduled Task that runs scripts/daily_scan.py
# once a day, so the dashboard DB stays current and `cli.py dashboard` starts fast.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1              # daily at 13:00
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -At 09:30
#   powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -Uninstall
#
# The task runs as the current user, only while logged on (no password stored),
# with pythonw.exe so no console window flashes. If the PC is off or asleep at
# the scheduled time, it runs as soon as possible afterwards.

param(
    [string]$At = "13:00",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "Claude Token Dashboard - Daily Scan"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $PSScriptRoot "daily_scan.py"

# Ask Python for its real path: Get-Command can return the Microsoft Store
# alias stub, which does not work from Task Scheduler.
$Python = (& python -c "import sys; print(sys.executable)").Trim()
if (-not $Python -or -not (Test-Path $Python)) {
    throw "Could not locate python.exe on PATH."
}
$Pythonw = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $Python }

$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Script`"" -WorkingDirectory $RepoRoot
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
    -Description "Incrementally scans ~/.claude/projects into the Token Dashboard SQLite DB." `
    -Force | Out-Null

Write-Host "Registered '$TaskName' - daily at $At."
Write-Host "  runs: $Pythonw `"$Script`""
Write-Host "  log:  $env:USERPROFILE\.claude\token-dashboard-scan.log"
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"
