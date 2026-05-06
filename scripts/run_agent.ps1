param(
    [string]$PythonBin = "",
    [string]$AgentConfigPath = "",
    [string]$DayKey = "",
    [string]$BaseDir = "",
    [switch]$EnableAfterHours,
    [switch]$Force,
    [switch]$DailyEvaluationOnly
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

if (-not $PythonBin) {
    $venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonBin = $venvPython
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            $PythonBin = $pythonCmd.Source
        } else {
            throw "Python executable not found. Set -PythonBin or create .venv."
        }
    }
}

if (-not $AgentConfigPath) {
    $AgentConfigPath = Join-Path $rootDir "config\agent_config.json"
}

if (-not $DayKey) {
    $DayKey = Get-Date -Format "yyyyMMdd"
}

if (-not $BaseDir) {
    $BaseDir = Join-Path $rootDir "data\daily\$DayKey"
}

$logDir = Join-Path $BaseDir "logs"
$todayLink = Join-Path $rootDir "data\today"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $rootDir "data\daily") | Out-Null

if (Test-Path $todayLink) {
    Remove-Item -LiteralPath $todayLink -Force -Recurse
}
New-Item -ItemType Junction -Path $todayLink -Target $BaseDir | Out-Null

$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$logFile = Join-Path $logDir "run_$ts.log"

function Test-ScheduleWindow {
    $pacificTz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Pacific Standard Time")
    $nowPt = [System.TimeZoneInfo]::ConvertTimeFromUtc((Get-Date).ToUniversalTime(), $pacificTz)
    $isWeekday = $nowPt.DayOfWeek -ge [System.DayOfWeek]::Monday -and $nowPt.DayOfWeek -le [System.DayOfWeek]::Friday
    $openPt = $nowPt.Date.AddHours(6).AddMinutes(30)
    $closePt = $nowPt.Date.AddHours(13)
    $evaluationEndPt = $nowPt.Date.AddHours(13).AddMinutes(15)
    return @{
        InRegularWindow = ($isWeekday -and $nowPt -ge $openPt -and $nowPt -lt $closePt)
        InFinalEvaluationWindow = ($isWeekday -and $nowPt -ge $closePt -and $nowPt -lt $evaluationEndPt)
        NowPt = $nowPt
        OpenPt = $openPt
        ClosePt = $closePt
        EvaluationEndPt = $evaluationEndPt
    }
}

if (-not $EnableAfterHours -and -not $Force) {
    $scheduleWindow = Test-ScheduleWindow
    if ($scheduleWindow.InFinalEvaluationWindow) {
        $DailyEvaluationOnly = $true
    } elseif (-not $scheduleWindow.InRegularWindow) {
        @(
            "Skipped scheduled run outside regular market schedule window."
            "Current PT time: $($scheduleWindow.NowPt.ToString('yyyy-MM-dd HH:mm:ss zzz'))"
            "Allowed scan window: weekdays 06:30 <= time < 13:00 PT"
            "Allowed final evaluation window: weekdays 13:00 <= time < 13:15 PT"
            "Use -Force for a manual off-hours run or -EnableAfterHours for after-hours processing."
        ) | Out-File -FilePath $logFile -Encoding utf8
        Write-Host "Skipped scheduled run outside allowed PT weekday windows. See $logFile"
        exit 0
    }
}

$arguments = @(
    (Join-Path $rootDir "stock_option_agent\agent.py")
    "--base-dir", $BaseDir
    "--universe-count", "50"
    "--config", $AgentConfigPath
)

if ($EnableAfterHours) {
    $arguments += "--enable-after-hours"
}

if ($DailyEvaluationOnly) {
    $arguments += "--daily-evaluation-only"
}

$stdoutFile = Join-Path $logDir "run_${ts}.stdout.log"
$stderrFile = Join-Path $logDir "run_${ts}.stderr.log"

$process = Start-Process `
    -FilePath $PythonBin `
    -ArgumentList $arguments `
    -WorkingDirectory $rootDir `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile `
    -NoNewWindow `
    -Wait `
    -PassThru

$stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { "" }
$stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "" }

@(
    $stdout
    if ($stderr) { "`n[stderr]`n$stderr" }
) | Out-File -FilePath $logFile -Encoding utf8

if ($process.ExitCode -ne 0) {
    throw "Agent run failed with exit code $($process.ExitCode). See $logFile"
}
