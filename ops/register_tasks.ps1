# Registers the two weekday Task Scheduler jobs:
#   SpyQqqBot-Posture  ~8:45 AM ET  (Claude risk posture, Job A)
#   SpyQqqBot-Trade    ~3:45 PM ET  (trading run, Job B)
#
# Times are converted from ET to this machine's local time at registration.
# The bot itself re-checks NYSE hours/holidays at runtime, so a DST edge week
# or a holiday only results in a harmless no-op run.
# Re-run this script any time to update (it overwrites existing tasks).

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

$etZone = [System.TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')

function Get-LocalTimeForEt([int]$Hour, [int]$Minute) {
    $nowEt = [System.TimeZoneInfo]::ConvertTime([DateTime]::UtcNow, $etZone)
    $etTarget = $nowEt.Date.AddHours($Hour).AddMinutes($Minute)
    $utc = [System.TimeZoneInfo]::ConvertTimeToUtc($etTarget, $etZone)
    return $utc.ToLocalTime()
}

$postureAt = Get-LocalTimeForEt 8 45
$tradeAt   = Get-LocalTimeForEt 15 45
$days = 'Monday','Tuesday','Wednesday','Thursday','Friday'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$jobs = @(
    @{ Name = 'SpyQqqBot-Posture'; Cmd = Join-Path $repo 'posture\run_posture.cmd'; At = $postureAt },
    @{ Name = 'SpyQqqBot-Trade';   Cmd = Join-Path $repo 'ops\run_bot.cmd';        At = $tradeAt }
)

$hider = Join-Path $repo 'ops\run_hidden.vbs'
foreach ($job in $jobs) {
    # wscript + run_hidden.vbs: no console window, so nobody can close (kill)
    # the job by accident; progress goes to logs\*.log instead.
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' `
        -Argument ('//B "{0}" "{1}"' -f $hider, $job.Cmd) -WorkingDirectory $repo
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $job.At
    Register-ScheduledTask -TaskName $job.Name -Action $action -Trigger $trigger `
        -Settings $settings -Description 'SPY/QQQ paper-trading bot (see spy-qqq-bot repo)' `
        -Force | Out-Null
    Write-Host ("registered {0}  ->  weekdays {1:HH:mm} local ({2})" -f $job.Name, $job.At, $job.Cmd)
}

Write-Host ''
Write-Host 'Sleep/wake check — Task Scheduler wake timers are unreliable on Modern Standby:'
powercfg /a
Write-Host ''
Write-Host 'If the output above says "Standby (S0 Low Power Idle)", do NOT rely on WakeToRun:'
Write-Host 'keep the PC awake during market hours (Settings > System > Power) or the runs'
Write-Host 'will fire late via "run as soon as possible after a missed start".'
